# Actions server (MCP)

The only place where actions run. It is a small MCP Server (official `mcp` SDK 2.x, stdio) that lets a client add, update and mark documentation as obsolete. It does not answer questions about the documentation: that is the job of the informational RAG + Knowledge Graph flow (see `design-decisions.md` D2, D6, D7).

Specification: `openspec/specs/mcp-actions-tools/spec.md` once the change is archived, until then `openspec/changes/add-mcp-actions-server/`.

## Tools

| Tool | Use it to | Arguments (required in bold) | Result |
| --- | --- | --- | --- |
| `add_document` | create a new markdown document, saying what it is about | **`service`**, **`doc_path`**, **`content`**, `about` | `outcome: created`; with `about`, also `about` (written) and `unresolved` (dropped names) |
| `append_to_document` | add text at the end of a document, or create it (nothing to quote) | **`service`**, **`doc_path`**, **`text`** | `outcome: appended` or `created` |
| `update_document` | replace one passage in an existing document | **`service`**, **`doc_path`**, **`old_text`**, **`new_text`** | `outcome: updated` or `outcome: conflict` |
| `link_document` | set what an existing document is about (replaces the list; an empty list removes it) | **`service`**, **`doc_path`**, **`about`** | `outcome: linked`, `about`, `previous`, `unresolved` |
| `mark_document_obsolete` | flag a document as outdated | **`service`**, **`doc_path`**, **`reason`**, `replaced_by` | `outcome: marked_obsolete` or `already_obsolete` |

- `service` is a lowercase slug of an existing service folder, for example `payments-service`.
- `doc_path` is relative to the service, ends in `.md`, and has no `..`, for example `docs/api-v2.md`. A path that starts with `repos/<service>/` (the workspace path shown in citations) is rejected with the path inside the service to use; nothing is written.
- Every schema is closed: an unknown argument is rejected.
- Invalid input is an **error result** (`is_error`) whose message names the argument. A **conflict** is a normal result: nothing is written and the caller decides what to do.

`append_to_document` is the simple way to record a new fact: it never needs the old text and never conflicts with it. The line ending style of the file is kept and a blank line separates the new text from the old. Two appends at the very same moment could overwrite each other (single-user workspace; no locking).

### Conflicts

`update_document` writes only if `old_text` appears **exactly once** in the current file. If it is gone (someone else edited the document) the outcome is `conflict` with the reason `text not found`; if it appears more than once, `text not unique`. The server never merges: the agent tells the user and retries with the exact current text.

### Obsolete documents

`mark_document_obsolete` adds a front-matter block to the document itself:

```markdown
---
status: obsolete
obsolete_reason: "Replaced by v2"
replaced_by: "docs/api-v2.md"
---
# original document...
```

Marking twice changes nothing. Ingestion can read this block later.

## Workspace

The tools never write to the committed sample data. They write to a **workspace**, a git-ignored working copy of the **whole** sample ecosystem (company, clients, repos, ...), so the same folder is also a complete data root that the knowledge graph and the index can read:

```bash
uv run python scripts/seed_workspace.py      # create, or reset to a fresh copy
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `DOCS_WORKSPACE` | `var/workspace` | Root of the workspace (`<root>/repos/<service>/...`) |
| `ACTIONS_AUDIT_FILE` | `var/audit/actions.jsonl` | One JSON line per successful write |
| `ACTIONS_CONFIRM_EDITS` | `on` | With `on`, `update_document` and `mark_document_obsolete` only return a preview (`outcome: needs_confirmation` with a `diff`) until the same call is repeated with `confirmed: true`. `off` writes at once. Creating and appending are never asked. |
| `ACTIONS_ALLOWED_SERVICES` | unset (all) | Comma separated services this session may write. A write to another one fails naming the allowed ones and writes nothing. |

The seed script replaces only its known entries (`company.yaml`, `company/`, `clients/`, `repos/`, `prs/`, the README), only inside a workspace it created itself (it leaves a `.seeded-workspace` marker), and refuses to touch anything else.

Written documents are **not searchable** until the index is synchronized: the server never touches the index. The agent's knowledge tool synchronizes before every question (see `docs/agent.md`).

Other variables: `ACTIONS_TOOLS_PACKAGE` (the tools package to load, default the real one; used by tests and demonstrations to start the server with another package) and `ACTIONS_LOG_LEVEL` (default `WARNING`, so a chat is not flooded by the server's INFO lines).

## Run it

```bash
uv run python -m ecosystem_assistant.actions.server     # speaks MCP over stdio
```

It is normally started by an MCP client (the agent). To exercise it by hand, use any MCP client, or the in-process tests.

## Add a tool

1. Create a module in `src/ecosystem_assistant/actions/tools/`, for example `reports.py`.
2. Define `register(server, workspace)` and declare the tool inside it with `@server.tool(description=...)`. The description must say when to use the tool and when **not** to.
3. Done. Restart the server. `server.py`, the existing tools and any agent code stay untouched; the new tool shows up in the tool listing with its own schema (`tests/actions/test_extensibility.py` proves it).

Modules whose name starts with `_` are ignored. A module that cannot be imported, or that has no `register`, stops the startup with an error naming it.

## Tests

```bash
uv run pytest
```

No test uses a real LLM or the network. `tests/test_architecture_isolation.py` fails if the actions package imports the retrieval, graph, agent or ingestion packages, or any LLM or network library.

## Document links

`about` is a list of exact names of services, APIs or events. The server checks them against the workspace (the service folders and the APIs and events their `service.yaml` declares); the names that match are written in the front matter of the document (`about: ["payments-api"]`) and the rest are not written and come back as `unresolved` with a hint, so a model can fix them or ask. `link_document` changes that one field of an existing document and returns the previous list, so a mistake can be undone; it never touches the text or other front matter fields. The knowledge graph reads the field (see [knowledge-graph.md](knowledge-graph.md)), and the next question already sees the new links because the agent refreshes the graph first.
