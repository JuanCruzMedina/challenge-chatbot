# Proposal

## Why

Criterion 5 of the brief asks for an architecture where tools are added without touching the routing logic. The tests prove it with throwaway tools, and `append_to_document` was a real addition, but its commit also edited the agent's prompt, so it is not a clean demonstration. The roadmap planned one: a new action tool, in its own new file, used by the agent with no change to the agent.

## What Changes

- Add the MCP tool `create_documentation_ticket(service, title, description, priority)` in a **new module** `actions/tools/tickets.py`. It records a request to write or fix documentation as a markdown file `tickets/DOC-0001.md` (the next free number) at the root of the workspace, outside `repos/`, with the service, title, priority, status `open`, creation date and description. It returns the ticket id and path and is recorded in the audit log.
- Show that the agent uses it with **no change to the agent**: a test runs the agent (real MCP server, scripted chat) and calls the new tool; and the implementation commit must touch nothing in `agent/`, `chat/`, `knowledge/` or `llm/` (checked with `git diff --stat` and reported).
- Update the tool lists in tests and docs that enumerate the server's tools (the only edits outside `actions/`; they are tests and documentation, not agent logic).

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `mcp-actions-tools`: the ticket tool.
- `agent-tool-routing`: the agent discovers and runs it without code changes.

## Impact

- New `src/ecosystem_assistant/actions/tools/tickets.py`, `tests/actions/test_tickets.py`, one agent-level test, docs.
- No new dependency, no model cost (tests are scripted).

## Non-goals

- Integration with a real ticket system (Jira, GitHub issues): tickets are files in the throwaway workspace.
- Listing, closing or editing tickets, assignees, due dates.
- Making tickets searchable by the informational flow (they live outside the indexed folders on purpose: a ticket is an action record, not documentation).
- Any change to the agent, the chat, the flow or the prompt.
