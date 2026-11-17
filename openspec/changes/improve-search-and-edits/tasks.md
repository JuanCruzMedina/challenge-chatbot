# Tasks

## 1. Graph queries
- [ ] 1.1 Write failing tests for the four `knowledge-graph-queries` scenarios, then implement `list_entities` and `team_overview`.
- [ ] 1.2 Write a failing test for the catalog scenario (also: every catalog method exists on the graph; the planning prompt describes both), then register both in `catalog.py` and the executor.

## 2. The append tool
- [ ] 2.1 Write failing tests for the three behavior scenarios (existing, missing, invalid input; newline style kept; audit entry), then implement `append_document` and register `append_to_document`.
- [ ] 2.2 Write the discovery test (real server lists the tool; its name is absent from `agent/`), and mutation-check by temporarily naming it in the agent.

## 3. The prompt
- [ ] 3.1 Write failing tests: the prompt has the three rules and names no MCP tool; a scripted turn after a confirmation writes once. Then update `prompts.py` (under 30 lines).

## 4. Docs and closing
- [ ] 4.1 Update `docs/agent.md` (tools table, prompt rules), `docs/informational-flow.md` (new queries) and `docs/roadmap.md`; keep the doc-example tests green.
- [ ] 4.2 Run the whole suite, the data validator and `OPENSPEC_TELEMETRY=0 openspec validate improve-search-and-edits --strict`; list scenario-to-test mapping.
- [ ] 4.3 (Optional, needs the user's yes and an announced estimate) Retry the Product Owner conversation with the real model and report whether it asks again after a "yes".
