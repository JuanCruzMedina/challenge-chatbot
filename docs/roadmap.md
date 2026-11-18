# Development path

Where the project stands, what comes next for the challenge, and the improvements worth making afterwards. Every improvement is tied to something that was **observed or measured** in this repository, so the list can be re-ordered with evidence instead of taste. Decisions already taken live in `design-decisions.md`; behavior lives in `openspec/specs/`.

## Where we are

| Area | Change (archived) | State |
| --- | --- | --- |
| Sample ecosystem | `extend-ecosystem-hierarchy` | Company, 2 clients, 3 applications, 7 services, a vision per client |
| Actions | `add-mcp-actions-server` | MCP Server with add, update (conflict-aware) and mark-obsolete tools |
| Graph | `add-knowledge-graph` | NetworkX graph with a plain-data query interface and provenance |
| Retrieval | `add-retrieval-index` | Chroma + MiniLM index, incremental sync, filtered cited search |
| Informational flow | `add-informational-flow` | LangGraph pipeline (plan, graph, documents, answer, check) on a model port |
| Agent | `add-agent` | **In progress**: tool-calling agent, runtime MCP discovery |

Working rules that apply to everything below: every step is a spec-driven change with tests first; **all tests run on scripted models, so they are fast, repeatable and free**; a run against the real local model (Ollama, no cost) is optional and only on request; nothing is pushed or published.

## The path to finish the challenge

| # | Step | Why now |
| --- | --- | --- |
| 1 | **Agent** (done) | The core criterion: the model alone chooses between the informational and the action route, and MCP tools are discovered at runtime |
| 2 | **Chat interface** (done; opening the web page is a manual step) | The brief asks for a passive, ready-made UI: a terminal chat first, then LangChain Agent Chat UI served with `langgraph dev` |
| 3 | **Extensibility demonstration** (done with throwaway tool modules in the tests and with `append_to_document`; a ticket tool was built and then removed as not useful) | A tool is added by adding one module to the server, and the agent uses it with no change to its code |
| 4 | **Check against the evaluation criteria** | Walk the six criteria of the brief with evidence from the tests and the measurements |
| 5 | Optional: expose the solution as an MCP Server for editors such as VS Code or Copilot | Listed as an optional extension in the brief |

## Improvements, with their evidence

### A. Linking documents to the things they are about

- **Built (2026-11-18).** Documents declare `about` (services, APIs, events) in their front matter; the graph reads it (relation `ABOUT`, query `documents_about`), and the chat writes it (`add_document`, `link_document`). **Not built:** links between documents (`[[…]]`) and backlinks, features and teams in `about`, filtering the index by link, and a model that proposes links for old documents at ingestion.

- **Observed.** The graph's relations come from hand-written manifests, and it reads only the documents a manifest lists. A document created from the chat is searchable (the index scans folders) but invisible to the graph. The model takes no part in connecting information.
- **Direction (chosen).** Explicit **tags and links in the document's front matter and text** (`tags: [payments-service]`, `[[runbook-failed-payments]]`), as in Obsidian, written by the model when it creates or edits a document and **validated by code** (names that match nothing are dropped and reported). The graph turns them into relations ("this document is about `notifications-service`") and gains backlink queries ("which documents mention `payments-api`?"); the index can filter by tag.
- **Asking as it goes.** The model fills in what it can from the conversation and the knowledge it just consulted; when it cannot tell what a document is about it asks **one** question whose options come from the graph; afterwards it says which links it added so the person can correct them with an update. The actions server helps without reading the graph: the result of a write lists tags and links that did not resolve in the workspace, so the model knows what is left to ask.
- **Evolution.** A later step, at ingestion, where a model proposes links for documents that have none, validated against the graph and stored as reviewable suggestions.
- **Risk.** A 7B model may forget a link. Validation prevents invented ones, not missing ones; it has to be measured.

### B. Keeping knowledge in step with the code

- **Ingestion from pull requests.** *First step built:* `python -m ecosystem_assistant.pr_review` reviews the documentation of a merged PR with the agent (see [pr-review.md](pr-review.md)); a real-model run of its review set is pending. What follows is below. The sample has one simulated PR. The next step is a function that applies a PR to the workspace so that graph and index follow; the retrieval sync and the graph rebuild already work per file, and the agent already refreshes before each question. Triggering from a real PR (a CI job or a webhook) comes after, with real repositories and a local model only (see `responsible-ai-usage`).
- **Read every document of a service, not only the listed ones** (observed in the retrieval change).
- **Real repositories.** Read OpenAPI files, `CODEOWNERS` and package manifests to build the graph instead of hand-written manifests.

### C. Trust in the answers

- **Observed.** In the real run, asked "who consumes the *ordres* api?", the model said that `orders-service` consumes it when the graph said it **provides** it and has no consumers, and it cited the right fact. The check verifies that citations exist, not that they are true; `grounded` means "cites existing evidence".
- **Ideas, cheapest first.** Render facts in plain sentences ("consumers: none", "provided by orders-service") instead of compact JSON; tune the answer prompt against the evaluation; a second pass that checks each claim against the cited item; a larger local model (for example 14B) for the answer stage.
- **Observed.** Questions about the domain whose answer is absent ("who is the CEO?") score as high as relevant ones, so no similarity threshold separates them. Ideas: an explicit "is this answerable from the evidence?" step, or a reranker.
- **Measure better.** The evaluation sets are small and written by the author; grow them, include misspellings and paraphrases, and keep the grading free of a judge model unless the cost is acceptable.

### D. Retrieval quality

- The offline embedder reached 0.86 and MiniLM 0.91 on 22 questions; a one-question difference proves nothing. Try hybrid keyword plus embedding search, a reranker and a stronger embedding model, comparing on a larger set.
- The documents of a real company are not all in English: check multilingual embeddings before using real documents.

### E. Writing safely and more widely

- **Confirmation before a write** (and a preview of what will change) as an option; today writes are automatic by design of the brief, into a throwaway workspace, and every write is audited.
- **Edit client and company documents from the chat.** The tools address documents by service, so visions and the company overview are read-only today; generalize the argument to a scope.
- **Cross-client relations** (shared services) and a richer relation vocabulary.

### F. Speed and operations

- An informational question costs about four model calls through the agent. Options: return the flow's answer directly when the turn is a pure question, cache the plan, a smaller model for planning.
- Compare local models (`llama3.1:8b`, `qwen2.5:14b`) on the same evaluations before changing the default.
- Run Ollama as a service (`brew services start ollama`) when the chat is used daily.

### G. Scale and platform

- **Graph store.** NetworkX is enough for this data; move to Kùzu when real repositories bring size, persistence across runs or several writers (decision D5). The query interface is the only thing that has to be re-implemented.
- **MCP over HTTP** with authentication, if the server is shared; several MCP servers behind one agent.
- **Memory.** Within a conversation the agent keeps the messages; remembering preferences across conversations is not planned.

## How to use this document

Each item becomes a change through the usual flow (`/opsx:propose`, apply, archive). Move an item up when new evidence makes it more valuable or more urgent, and record what was measured when it is done.
