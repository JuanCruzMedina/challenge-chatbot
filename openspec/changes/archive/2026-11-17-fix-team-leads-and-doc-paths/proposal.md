# Proposal

## Why

Trying the chat with the real model showed three defects:

1. "List every team and who leads each" answered that the leads are unknown. The graph knows them, but a question about all teams needs seven `team_overview` calls and the plan is limited to four queries.
2. Asked to add a line to the README of `driver-service`, the agent passed the path it saw in a citation (`repos/driver-service/README.md`). The tool expects a path inside the service, so it created a new file at `repos/driver-service/repos/driver-service/README.md`, reported `created`, and left the real README untouched.
3. Asked to record a Product Owner that the documentation never mentions, the agent asked for confirmation as if there were a contradiction. Missing data is not a contradiction.

## What Changes

- New graph query `teams_overview` (no arguments): every team with the services it owns and each service's lead, in one call. It is added to the plan catalog.
- Each passage returned by `query_knowledge` also carries `service` and `doc_path` (the path inside the service), so the agent never has to derive them.
- The MCP write tools reject a `doc_path` that starts with `repos/<service>/` and say which path inside the service to use. Nothing is written in that case.
- The prompt states that data the documentation does not mention is new, not a conflict, and is written without asking.
- The real-model routing evaluation gains regression turns for the three defects.

## Capabilities

### Modified Capabilities
- `knowledge-graph-queries`, `knowledge-flow-answers`, `mcp-actions-tools`, `agent-tool-routing`.

## Impact

- `knowledge/graph/queries.py`, `knowledge/flow/{catalog,answer}.py`, `actions/workspace.py`, `agent/prompts.py`, `evaluation/agent.yaml`, tests, docs. The real-model run is announced first (about $0.03).

## Non-goals

- Reading `service.yaml` or other non-markdown files.
- Changing how passages are ranked or the embedder.
- Answering about teams without a service (the graph has none).
