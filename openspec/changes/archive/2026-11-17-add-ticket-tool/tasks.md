# Tasks

## 1. The tool
- [x] 1.1 Write failing tests for the ticket scenarios (numbering, front matter, audit entry, invalid input, simultaneous creation, not indexed), then implement `actions/tools/tickets.py` with `create_ticket` and `register`.
- [x] 1.2 Write the schema test (description with "Do NOT use", closed schema, required arguments) and make it pass.

## 2. The demonstration
- [x] 2.1 Write the agent-level test (real server, scripted chat calls the tool, file exists) and update the tests and docs that list the server's tools.
- [x] 2.2 Run the whole suite; confirm the "no tool name in the agent" test passes; confirm with `git diff --stat` that nothing under `agent/`, `chat/`, `knowledge/` or `llm/` changed, and record it in `docs/evaluation-criteria.md` (criterion 5) with the commit.

## 3. Closing
- [x] 3.1 Update `docs/actions-server.md`, `docs/agent.md` and `docs/roadmap.md`; run the suite, the data validator and `OPENSPEC_TELEMETRY=0 openspec validate add-ticket-tool --strict`; map scenarios to tests.
