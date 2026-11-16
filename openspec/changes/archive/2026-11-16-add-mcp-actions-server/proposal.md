# Proposal

## Why

The challenge requires every action to go through an MCP Server, strictly separate from the informational RAG + Knowledge Graph flow. The vision is that people add and update documentation from the chat, while the files stay the single source of truth that a separate ingestion later turns into the index and graph. The server is built before the agent, so the agent is written against a real tool surface.

## What Changes

- Add a minimal MCP Server (official Python SDK, stdio transport) with three documentation tools over the invented "Demo Grocery" ecosystem:
  - `add_document`: creates a new document for a service.
  - `update_document`: replaces a passage inside an existing document; it reports a conflict instead of writing when the passage the caller saw is no longer there.
  - `mark_document_obsolete`: flags a document as obsolete in the document itself.
- Every tool publishes a correct MCP schema: a name, a description that says when to use it, and a strict JSON Schema `inputSchema`.
- Tools are registered by dropping one module into a tools package; the server finds it at startup. Adding a tool needs no change to the server entry point and none to agent code.
- The tools write only to a configurable **workspace** (a git-ignored working copy of the sample repos, seeded by a script). The committed sample data stays a read-only baseline.
- Every successful write is appended to an audit log.
- The server has no dependency on the vector store, the knowledge graph or any LLM, and runs offline. It never touches the index: indexing is the job of the ingestion change.

Routing invariant restated (see `openspec/config.yaml`): actions go only through this MCP Server; informational queries never do.

## Capabilities

### New Capabilities
- `mcp-actions-tools`: the MCP Server contract: tool discovery and schemas, the three documentation tools with conflict handling, the workspace and audit log, extensibility by tool registration, and isolation from the informational flow.

### Modified Capabilities
<!-- None: openspec/specs/ is empty. -->

## Impact

- New Python package and `pyproject.toml` (local `uv` venv, Python 3.12; dependencies `mcp`, `pytest`). Nothing is installed globally; `uv` caches a Python download, which needs the user's go-ahead first.
- New folders: `src/ecosystem_assistant/actions/`, `tests/`, `var/` (git-ignored), and `scripts/seed_workspace.py`.
- No change to `data/ecosystem/` or the validator; no network or LLM calls, tests included.

## Non-goals

- Re-indexing after a write: ingestion is a later change; until then a written document is not searchable.
- The company, client and application hierarchy in the sample data (a separate change).
- Merging text automatically: a conflict is reported to the caller, never resolved by the server.
- Authentication, multiple users or concurrent writers: a single local process is assumed.
- Pull-request or approval flows for edits; direct writes with a conflict check are enough for the challenge.
- The agent, the MCP client and tool discovery on the agent side (a later change).
