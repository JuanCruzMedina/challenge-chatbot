# Tasks

## 1. Removal
- [x] 1.1 Delete the tool module and `tests/actions/test_tickets.py`; remove the ticket test from `tests/agent/test_prompt_rules.py` and the tool name from every list of tools in tests and docs; confirm the suite is green.
- [x] 1.2 Update `docs/evaluation-criteria.md`, `docs/roadmap.md`, `docs/design-decisions.md` and `docs/actions-server.md`; remove the local `var/workspace/tickets/` folder.
- [x] 1.3 Run the suite, the data validator and `OPENSPEC_TELEMETRY=0 openspec validate remove-ticket-tool --strict`.
