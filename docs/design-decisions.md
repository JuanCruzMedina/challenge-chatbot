# Design decisions

Challenge: *Multi-Source Chatbot with Intelligent Agent Orchestration*.
Status: **draft v1** (2026-11-16). Each decision carries its status: `accepted`, `proposed` or `future`.

> Cross-cutting rule: all data in this repo is **invented**. No real CraftLabs, client or personal information. See `responsible-ai-usage` in the vault.

---

## D1. Use case — accepted

**Documentation assistant for a microservices ecosystem** (multi-repo) that joins the product view with the code view.

- **Informational queries:** RAG over documentation (guides, runbooks, ADRs, product specs) + an ecosystem KG.
- **Actions (via MCP):** for example `create_documentation_ticket`, `mark_document_obsolete`, `assign_reviewer`.
- **Future vision:** the index and the KG update themselves when PRs are merged, giving a global understanding of services, APIs, dependencies and owners, and how they relate to product features and epics.

Scope inside the challenge: an invented ecosystem of 3 to 4 microservices in fake local git repos, plus a product document.

## D2. Ingestion separated from chat — accepted

Knowledge updates are a **separate pipeline**, not a chat action.

```text
Repos / PRs ──► INGESTION (pipeline, no chat) ──► vector index + KG
                                                       │
User ──► Agent ──► tool "query_knowledge" ─────────────┘   (read-only)
           └─────► MCP tools (actions, separate)
```

- Scope in the challenge: **simulated and incremental**. A single function `ingest(repo, commit_range)` takes the diff of a simulated PR and reindexes only what changed. It is invoked by script, with no GitHub Actions and nothing published.
- It processes only: documentation markdown, service manifests (owner, dependencies, APIs) and the PR text. It does **not** parse source code (future).
- Every chunk and node stores `repo`, `commit`, `file` and date, so it can delete and reindex incrementally and cite versioned sources.
- The chat agent **only reads** knowledge. Actions requested by the user always go through the MCP Server.
- Open point: this is an interpretation of the brief ("the MCP Server is the only valid mechanism for executing actions"). Ingestion is a system process, not a user action. If it matters for the evaluation, confirm it with the lead.

## D3. Orchestration: LangGraph — accepted

- **Why:** the informational graph (retrieve, query KG, synthesize) stays explicit as a `StateGraph`. The agent decides with tool-calling, with no `if/else`. LangChain Agent Chat UI, the recommended UI, connects directly to LangGraph graphs.
- **Rejected alternatives:** plain LangChain agents (the centralized pipeline is less visible), CrewAI (built for agent teams), a hand-written loop with the SDK (no ready-made UI).

## D4. Vector store: local Chroma — accepted

- **Why:** persists to disk, needs no server, and keeps per-chunk metadata (required for incremental ingestion).
- **Alternatives:** FAISS (metadata and deletes are awkward), LanceDB (comparable), Qdrant or pgvector (better in production, need a server).
- **Embeddings:** a local model (`sentence-transformers`). Nothing leaves the machine and it costs nothing.

## D5. Knowledge Graph: NetworkX — accepted · Kùzu in the future

**Today: in-memory NetworkX, loaded from JSON.**

- **Why:** zero infrastructure, and ecosystem queries (dependents, paths, change impact) are graph traversals that NetworkX handles well.
- **Known limits:** it is not a database (no own persistence, no concurrency, no query language) and it does not scale to very large graphs.
- **Mitigation:** the KG is accessed **only** through our own query interface (for example `dependents_of(service)`, `owner_of(doc)`, `path(a, b)`). No other code touches NetworkX directly.

**Recommended future option: Kùzu** (embedded graph database with Cypher).
- When to migrate: when moving to real repos, or with many nodes, persistence across runs, expressive queries (text-to-Cypher) or several processes writing (ingestion and chat at the same time).
- Migration cost: reimplement the query interface on Kùzu and load the same nodes and relations. The rest of the system does not change.

**If usage becomes multi-user or team-wide: Neo4j or Memgraph** (server-based).

## D6. MCP Server: official Python SDK (`FastMCP`), stdio — accepted

- It is the **only** mechanism for executing actions, and it is not part of the informational graph.
- Correct MCP schemas: a name, a clear description and an `inputSchema` (JSON Schema) on every tool.
- Tools are **discovered dynamically** by an MCP client (`langchain-mcp-adapters`). Adding a new tool does not touch the agent.
- Actions operate on invented, local data. Nothing is published.

## D7. Agent and routing — accepted

- The agent is an LLM with tool-calling and receives two kinds of tools:
  1. **One** tool `query_knowledge`, which encapsulates the whole informational graph (RAG + KG).
  2. The MCP Server's tools, listed at startup.
- **The model** decides the route from the tool descriptions. `if/else` and keyword routing are **forbidden** in the agent logic.
- Tool descriptions are part of the design: they are what the model uses to decide.

## D8. UI: terminal first — accepted

- A passive terminal REPL, with no frontend of our own. Afterwards, **LangChain Agent Chat UI** via `langgraph dev` if time allows.
- The UI only forwards messages and prints replies.

## D9. LLM and spend policy — accepted (revised 2026-11-16: **Ollama by default**)

**Context:** the budget is personal. The goal is to spend as little as possible, ideally nothing.

**Decision:** the default LLM is **local, through Ollama** (zero cost, nothing leaves the machine). The Anthropic API stays as an **optional alternative**, off by default, and is used only with explicit approval.

- Development machine: 18 GB of RAM, Apple Silicon. The target is a quantized 7 to 14B model with tool-calling support. The exact model is chosen and measured in step (d).
- Ollama is not installed yet. Installing it is a global change and happens only with prior notice.
- Main risk: small local models choose between tools less reliably. Mitigated with very clear tool descriptions and a small set of test cases, and the results are documented.
- The provider is defined in **one place** (an environment variable), so switching to the API does not touch the agent.

### Alternative with the Anthropic API (not the default)

**Model:** Claude **Haiku 5.5** (`claude-haiku-5-5`), the cheapest of the family.
- Price: $0.10 per million input tokens and $0.50 per million output tokens (prompts up to 100K tokens).
- Estimate (not measured): ~18K input and ~1.5K output tokens per query, about **$0.0025 per query**. $1 covers roughly 400 queries.
- Low effort (`effort: low`) to save reasoning tokens.
- **No move to Sonnet 5.5 or Opus 5.5 without explicit approval.** Sonnet costs about 20 times more per token.
- Risk: a small model may pick the wrong tool. It is measured in the test stage, and if it fails that is documented before spending more.

**Controls to stay within budget** (they apply only if the API is enabled):
1. **A hard cap on the Anthropic account (the only real guarantee).** Load only a small prepaid credit, for example $5, with auto-reload **off**, and set a spend limit in the Console if available. The user does this.
2. **A cap in code.** A persistent counter of tokens and estimated cost that **aborts** calls once the configured limit is exceeded (proposal: **$1.00 total**, adjustable).
3. **Tests do not use the real LLM.** Automated tests use a fake model with fixed answers. Real calls are few, manual and require an explicit variable (`LIVE_LLM=1`).
4. **Before each batch of real calls, the user is told** how many calls and the estimated cost.
5. **Local embeddings**, at zero cost.
6. Prompt caching and short outputs where possible.

**Note:** a Claude subscription does not include API credits. The API is billed separately in the Console.

## D10. Environment — accepted

- Python with `uv` and a venv inside the repo. Nothing global.
- `.env` for keys, ignored by git. No push and nothing published.

## D11. Process and language — accepted (2026-11-16)

Modeled on the way of working in `recruiting-metrics`, in a **lightweight** version (no skills copied from that repo, and no information from it).

- **Language:** code, comments, file names, docs and specs in **English**. The conversation with the user stays in Spanish.
- **Spec-driven with OpenSpec:** one change per step under `openspec/changes/<name>/`. Specs in Given-When-Then, with at least one test per scenario. A proposal under 500 words with a `Non-goals` section. Tasks of up to 2 hours, in TDD order.
- **`AGENTS.md`** is the single source of rules; `CLAUDE.md` only points to it.
- **Git:** `feature/<name>` branches and Conventional Commits. **No commit and no push without the user's explicit yes.** Nothing is published.

---

## Risks and open items

| Risk | Mitigation |
|---|---|
| The local model picks poorly between the informational and the action route | Very clear tool descriptions, a small set of test cases, document the results before changing model |
| Spend gets out of hand (only if the API is enabled) | The D9 controls, mainly the cap on the account |
| Ingestion gets mistaken for a chat action | D2, and confirm with the lead if needed |
| Real data in the future | Local or client-approved embeddings and LLM, per `responsible-ai-usage` |
| NetworkX falls short | An isolated query interface (D5) and migration to Kùzu |

**To confirm:** the interpretation of D2 with the lead, and whether the optional API gets enabled (and with which cap).
