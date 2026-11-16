# Design

## Context

- Greenfield Python code: the repo has the sample data, the validator script and the OpenSpec scaffold. The behavior contract is in `specs/mcp-actions-tools/spec.md`; motivation is in `proposal.md`.
- Decisions D2 (ingestion separate from chat), D6 (MCP Server, official SDK, stdio), D7 (the agent routes by tool-calling) and D9 (local LLM, no spend) in `docs/design-decisions.md` apply. D2 is refined by this change: the chat may **write documentation sources** through the MCP Server, but it never writes the index; ingestion is the only thing that builds the index.
- The agent will route using tool descriptions, so descriptions are part of the product and a small local model must be able to choose from them.
- The server and the agent run in separate processes. The agent will start the server over stdio and list its tools; this change builds only the server side.

## Goals / Non-Goals

**Goals:**
- A small server whose tool surface is extended by adding a file.
- Tool schemas generated from typed signatures so schema and behavior cannot drift.
- Safe writes: confined to a workspace, atomic, audited, conflict-aware.
- Fully testable offline, with no LLM and no network.

**Non-Goals:**
- A plugin system with versioning, configuration or hot reload.
- Any agent-side code, any indexing, any text merging.

## Decisions

**D-1. Official `mcp` SDK (2.x) with `MCPServer`, stdio transport.** Tools are plain typed functions registered with the SDK decorator, and the SDK derives `inputSchema` from the type hints. In `mcp` 2.x the class `FastMCP` was renamed `mcp.server.mcpserver.MCPServer`, so the dependency is pinned to `mcp~=2.3`. Alternatives: the third-party `fastmcp` package (more features, another dependency) and a hand-written JSON-RPC loop (more code, more room for schema errors). The API was verified against the installed 2.3.0 before use (task 1.3).

**D-2. Auto-discovery of tool modules.** `server.py` builds the server and imports every module in `ecosystem_assistant.actions.tools` with `pkgutil.iter_modules`; each module exposes `register(server, workspace)` and registers its tools there (no global state, so tests inject a temporary workspace). Adding a tool is adding a file. Alternatives: an explicit import list in `server.py` (adding a tool edits the entry point, which the spec forbids) and entry points (heavier than needed). An import error aborts startup with the module name; modules whose name starts with `_` are skipped.

**D-3. A workspace, not the committed data.** Tools read and write under `DOCS_WORKSPACE` (default `var/workspace/`, git-ignored). `scripts/seed_workspace.py` copies `data/ecosystem/repos/` into it, so the committed sample stays a clean baseline and a demo can be reset in one command. Layout: `<workspace>/repos/<service>/...`. Alternative: write straight into `data/ecosystem/` (every demo would dirty git).

**D-4. Conflict check by passage, not by hash.** `update_document` takes the exact passage the caller saw (`old_text`) and its replacement. It writes only if that passage occurs exactly once; otherwise it returns a `conflict` outcome. This is the same optimistic check as a version comparison, but the agent needs no file hash and does not have to read the whole file: it quotes text it already got from the knowledge answer. A conflict is a successful tool result carrying `outcome: "conflict"` and a `reason`, so the agent can explain it and ask the user; reserving `isError` for invalid input. Alternative: a content hash plus a read tool (more steps, and a read tool would blur the informational boundary).

**D-5. Obsolete status lives in the document.** `mark_document_obsolete` prepends a front-matter block (`status`, `reason`, `replaced_by`). Ingestion can read it later and the RAG can down-rank or flag the document. No separate database or ledger. Idempotent: if the front matter already says obsolete, the file is left untouched.

**D-6. Validate against the workspace, never the knowledge graph.** `service` must be a folder that exists in the workspace, and the error lists the valid ones; the server never consults the index or the graph to decide. A model that invents a service name gets a clear error. This keeps the action side independent from the informational side.

**D-7. Path safety and atomic writes.** `service` is a slug (`^[a-z0-9-]+$`), `doc_path` is relative, ends in `.md` and has no `..`. The resolved target must stay inside the workspace (symlinks included). Writes go to a temporary file in the same directory and are renamed over the target.

**D-7b. Deliberate errors use `ToolError`.** Verified in 2.3.0: any other exception is treated as a crash and the model only sees `Error executing tool <name>`. Validation failures the spec requires to name the offending argument therefore raise `mcp.server.mcpserver.exceptions.ToolError` with the message, which reaches the model with `is_error=True`.

**D-7c. Closed schemas through a small adapter.** The SDK generates input schemas without `additionalProperties: false` and silently accepts unknown arguments, but the spec requires closed schemas. After the tools are registered, an adapter in `server.py` sets `additionalProperties: false` on every tool schema and switches each argument model to `extra="forbid"`. It touches SDK internals (`_tool_manager`), so it is isolated in one function, guarded by the `mcp~=2.3` pin, and covered by a discovery test that fails if the schema is not closed or an unknown argument is accepted.

**D-8. Audit log.** Each successful write appends one JSON line (`action`, `service`, `path`, `timestamp`) to `var/audit/actions.jsonl` (location from `ACTIONS_AUDIT_FILE`). It makes demos traceable without a database.

**D-9. Testing strategy.** Unit tests per tool function against a temporary workspace; in-process MCP client tests for discovery, schemas and error results; one subprocess smoke test over stdio. An architecture test parses package imports and fails on retrieval, graph, agent or LLM-library imports. The extensibility test copies a throwaway tool module into a temporary tools package, so the real tools directory is never edited. No test uses an LLM.

**Layout:**

```text
src/ecosystem_assistant/actions/
  server.py        # builds FastMCP, discovers tool modules, main()
  workspace.py     # safe path resolution, atomic write, audit log
  tools/
    documents.py   # add_document, update_document, mark_document_obsolete
scripts/seed_workspace.py
tests/actions/
```

## Risks / Trade-offs

- **SDK API drift** → check the installed `mcp` version's API first and pin it in `pyproject.toml`.
- **Weak tool descriptions mislead a small local model** → each description says when to use and when not to use the tool; a test enforces a minimum; real routing quality is measured in the agent change.
- **A passage the model quotes slightly wrong yields a false conflict** → the conflict reason says the text was not found, so the agent can retry with the exact text; accepted for the challenge.
- **No merging** → a human resolves conflicts; automatic merging is out of scope.
- **Written documents are not searchable until ingestion runs** → documented in the tool results and in `docs/actions-server.md`.
- **Concurrent writers could still race between read and rename** → out of scope (single process); atomic rename prevents a torn file.
- **`uv` downloads Python 3.12 to the user cache** → ask the user before the first run; nothing is installed globally.
