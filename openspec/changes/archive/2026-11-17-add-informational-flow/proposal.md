# Proposal

## Why

The knowledge graph and the retrieval index exist, but nothing combines them. The challenge requires that every informational question goes through one centralized flow that gathers and synthesizes facts from the graph and passages from the documents. This change builds that flow as a single function, `ask(question)`, which the agent will later expose as its one knowledge tool. It also builds the language-model layer the flow needs, and that the agent will reuse.

## What Changes

- Add a provider-neutral LLM port with two implementations: a scripted fake for tests and an Ollama adapter for local models (no cost, nothing leaves the machine). The provider is chosen by configuration.
- Add a centralized pipeline on LangGraph: **plan, graph queries, document search, answer, check**. The model plans which graph questions to ask, from a fixed catalog, and the plan is validated before anything runs. Document search always runs. The model then writes the answer from numbered evidence.
- Every answer carries citations to graph facts and document passages, a status (`answered`, `insufficient_evidence` or `degraded`), a grounded flag, and a trace of what was run. Citations the model invents are removed.
- When there is no evidence, the flow says so without calling the model. When the model returns invalid output or fails, deterministic fallbacks apply and the answer is marked degraded.
- Retrieval results below a minimum score count as no evidence; the default is calibrated on the evaluation questions.
- Add an end-to-end evaluation set and script, graded without a judge model: by the sources the answer cites and the key facts it states.

Routing invariant restated (see `openspec/config.yaml`): this is the informational path only. It never calls the MCP actions server and cannot execute actions; the agent will expose it as one tool.

## Capabilities

### New Capabilities
- `knowledge-flow-answers`: the centralized flow, its planning and validation, grounded answers with citations and statuses, fallbacks, the LLM port, and the evaluation.

### Modified Capabilities
<!-- None. -->

## Impact

- New packages `ecosystem_assistant.llm` and `ecosystem_assistant.knowledge.flow`, tests under `tests/flow/` and `tests/llm/`, and a script `scripts/eval_flow.py`.
- New runtime dependencies `langgraph` and the `ollama` Python client (small, local venv only). `openspec/config.yaml` gains the module `knowledge-flow`.
- Ollama itself (a global install plus a model of several GB) is needed only for manual quality runs, never for the tests, and only with the user's explicit go-ahead.
- No change to the data, the graph, the index or the actions server.

## Non-goals

- The agent and the choice between informational and action routes (the next change).
- Action tools, UI, streaming, multi-turn memory.
- Prompt optimization beyond a working baseline, and a judge model.
- Paid APIs and reranking.
