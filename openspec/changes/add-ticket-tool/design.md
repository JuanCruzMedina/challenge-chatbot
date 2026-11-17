# Design

## Context
Invariants and motivation in `proposal.md`. The server registers every public module of `actions/tools/` that has `register(server, workspace)`; the agent lists tools at the start of every turn.

## Decisions

**D-1. A new module, not an edit of `documents.py`.** The point is a diff that adds a file and changes no routing code. `tickets.py` follows the pattern of `documents.py` (behavior function + `register`), with the same closed schema, slug pattern for `service` and a description that says when to use and when not to.

**D-2. Where tickets live.** `<workspace>/tickets/DOC-NNNN.md`, outside `repos/`, so that the retrieval index and the graph (which read services, clients and the company folder) do not see them. A test checks that after creating a ticket the index sync does not add it. Alternative: inside the service's `docs/`; rejected, a ticket is not documentation and would pollute answers.

**D-3. The id.** The next number after the highest `DOC-NNNN` present (4 digits). Creation uses an exclusive-create write, so two simultaneous calls cannot overwrite each other: the loser retries with the next number (bounded to a few attempts, then a clear error).

**D-4. Content.** Front matter (`id`, `service`, `title`, `priority`, `status: open`, `created` in UTC ISO date) and the description as the body. `priority` is one of `low`, `normal`, `high` (default `normal`). The service must exist (same check as the other tools). Title and description must be non-empty; the title is one line (newlines are rejected).

**D-5. The demonstration.** Evidence is (a) an agent test with the real server over stdio where the scripted chat calls `create_documentation_ticket` and the file appears, (b) the existing "no tool name in the agent source" test still green, (c) the commit's file list with nothing under `agent/`, `chat/`, `knowledge/`, `llm/`.
