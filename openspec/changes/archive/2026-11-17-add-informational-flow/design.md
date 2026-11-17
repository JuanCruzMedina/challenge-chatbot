# Design

## Context

- The graph (`ecosystem_assistant.knowledge.graph`) answers structural questions with plain data and sources; the index (`ecosystem_assistant.knowledge.retrieval`) returns cited passages with a score. Behavior contract: `specs/knowledge-flow-answers/spec.md`; motivation: `proposal.md`.
- Decisions D3 (LangGraph), D7 (the agent routes by tool-calling; the informational graph is one tool) and D9 (local LLM through Ollama, no spend) in `docs/design-decisions.md` apply. Ollama is not installed yet, so everything except quality measurement must work without it.
- The retrieval has no relevance threshold (recorded as a limit in `docs/retrieval-index.md`); this flow is where it gets one.
- The agent, in the next change, will reuse the model layer; here the model is used only inside the flow.

## Goals / Non-Goals

**Goals:**
- One centralized pipeline for every informational question, easy to read as a graph.
- Answers that can be checked: numbered evidence, validated citations, honest statuses.
- A model layer where nothing depends on a provider, and a flow whose tests need no model at all.

**Non-Goals:**
- Choosing between informational and action routes (the agent).
- Multi-turn memory, streaming, prompt optimization, a judge model.

## Decisions

**D-1. A small model port.** `LLM` has `name`, `complete(system, user) -> str` and `complete_json(system, user, schema) -> dict`. Two errors: `LLMUnavailableError` (cannot reach the model, with how to start it) and `LLMOutputError` (the model answered but not with valid JSON). The flow imports only this port. Alternative: use LangChain chat models directly; rejected here because it ties the tests to LangChain's fake models and tool-binding rules. The agent change will build a LangChain chat model from the same settings where it needs native tool-calling.

**D-2. Two implementations.** `ScriptedLLM` replays a list of responses (text, dict, or an exception to raise) or calls a responder function, records every call, and fails with a clear error when the script runs out; it makes the flow fully testable. `OllamaLLM` uses the `ollama` client with `format` set to the JSON schema, temperature 0 and a timeout; it maps a connection failure to `LLMUnavailableError` naming the address and `ollama serve`. Settings come from `LLM_PROVIDER` (`ollama` default, `fake`), `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`. Alternative: also an Anthropic adapter; out of scope, since the decision is a free local model (D9).

**D-3. The pipeline is a LangGraph `StateGraph`.** State: question, plan, facts, passages, answer, citations, status, trace. Nodes: `plan`, `graph_queries`, `document_search`, `answer`, `check`. After `document_search`, a conditional edge goes straight to the end when there is no evidence (design D-7). This edge is a sufficiency guard on data, not a choice between informational and action routes, which stays the agent's.

**D-4. The plan is one JSON object, validated.** The model returns `{graph_queries: [{method, arguments}], filters: {client, application, service}, include_obsolete}`. The catalog is fixed in code: `client_overview(client)`, `application_services(application)`, `service_owner(service)`, `api_consumers(api)`, `event_flow(event)`, `service_product_context(service)`, `relation_path(start, end)`, `describe(entity)`, `obsolete_documents()`. Validation drops unknown methods and queries with missing or extra arguments (recording the reason), cuts to four queries, and drops filters naming clients, applications or services that the graph does not know. Entity names are passed to the graph's tolerant matching. Invalid JSON is retried once with the error appended; then the flow continues with a document search alone. Alternative: a native tool-calling loop; rejected for this stage because small local models are more reliable returning one JSON object than driving a multi-turn tool loop, and a plan can be validated and tested. Native tool-calling matters where the model must choose between informational and action tools, which is the agent.

**D-5. Evidence is numbered and bounded.** Each executed graph query becomes a fact `K<n>` (compact JSON of its result, truncated with a marker, plus its source files). A query whose entity is not found becomes a fact that says so and lists the suggestions, so the model can say "did you mean". Passages from the search that reach the minimum score become `D<n>` (heading path, text, file). The search asks for five passages. The total evidence is capped at about 9000 characters for a small local context; the lowest-scoring passages go first.

**D-6. Sufficiency guard and minimum score.** If no graph query found anything and no passage reaches `min_score`, the flow returns `insufficient_evidence` with a fixed message and does not call the model for the answer. `min_score` is a parameter whose default depends on the embedder, because scores are not comparable across embedders; the defaults are calibrated on the evaluation questions (task 5.1) and recorded with the measured numbers. Passages below it never reach the model.

**D-7. The answer is JSON too.** The model returns `{answer, citations}` with ids from the evidence. The check stage removes ids that do not exist (recording them), resolves each valid id to its sources (graph source files, or document path and heading), and sets `grounded` when at least one valid citation remains. Prompts are English module constants, written to say: use only the evidence, cite ids, say when the evidence is not enough.

**D-8. Fallback ladder, never a silent provider swap.** Plan fails twice: document search only, status `degraded`. Answer fails or is invalid twice: an answer composed from the evidence itself (the facts in one line each and the best passages with their sources), status `degraded`, `grounded` false. `LLMUnavailableError` is not caught: it propagates with its message, because replacing the model silently would hide a broken setup.

**D-9. The answer is a dataclass with `to_dict()`.** Fields: question, text, status (`answered`, `insufficient_evidence`, `degraded`), grounded, citations (id, kind, label, sources), trace (stages with outcome, dropped plan items, removed citations, retries). The agent will pass it on as the tool result.

**D-10. Flow evaluation without a judge model.** `evaluation/flow.yaml`: each question has a kind (`graph`, `document`, `combined`, `unknown`), the sources an answer should cite (document paths or graph entity ids) and key facts (case-insensitive substrings that must appear in the text). A question passes when the status and grounding are right, an expected source is cited and every key fact appears; an `unknown` question passes when the status is `insufficient_evidence`. Automated tests exercise the script with a scripted model; the real measurement uses Ollama, manually.

**D-11. Where things live.** `ecosystem_assistant.llm` (port, scripted, Ollama, settings), `ecosystem_assistant.knowledge.flow` (catalog, plan, evidence, nodes, graph, answer, prompts). The actions server stays forbidden from importing either.

## Risks / Trade-offs

- **A 7B local model plans poorly or ignores the JSON format** → the plan is validated, the fallback ladder keeps answers honest, and the evaluation tells how often it works.
- **The model cites correctly but states something the evidence does not say** → the check verifies ids, not truth; this is a known limit, mitigated by showing sources and by the evaluation's key-fact checks.
- **Scores differ per embedder, so one threshold does not fit all** → defaults per embedder, calibrated and recorded.
- **LangGraph and the Ollama client change quickly** → verify installed APIs first (task 1.2) and pin versions.
- **Local latency** → temperature 0, bounded evidence, one retry at most per stage; timings are not asserted in tests.
- **Ollama is a global install** → only for manual measurement, and only with the user's go-ahead.
