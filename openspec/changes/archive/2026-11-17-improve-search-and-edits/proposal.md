# Proposal

## Why

A real session in the web chat showed three problems:

1. Asked to list all teams and who is in them, the knowledge tool answered "teams not found". The graph has team and person nodes, but no query lists every entity of a type or shows a team with its services and leads.
2. To record a new fact (two Product Owners) the agent proposed editing `service.yaml`, which the write tools cannot touch, and then asked for confirmation three times after the person had already said "yes".
3. Editing an existing document needs the exact old text, which the agent cannot read, so a simple "add this" is hard.

## What Changes

- Knowledge graph: two new queries, `list_entities(type)` (every team, person, service, ...) and `team_overview(team)` (the team, its services and their tech leads). Both are added to the flow's query catalog, so the planner can choose them; the agent is not touched.
- MCP server: one new tool, `append_to_document(service, doc_path, text)`. It adds text at the end of a markdown document and creates the document when it does not exist. No exact text is needed. Discovered by the agent at runtime.
- Agent system prompt (still naming no tool): a confirmation from the person is the order to act; ask again only when the tool needs a value that is unknown. Before writing a fact that may contradict the documentation, check with the knowledge tool; ask the person only if it does contradict. Write tools handle markdown documents only: new facts go to a document.
- Documentation of all of the above.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `knowledge-graph-queries`: `list_entities`, `team_overview`.
- `knowledge-flow-answers`: the planning catalog offers both queries.
- `mcp-actions-tools`: `append_to_document`.
- `agent-tool-routing`: prompt rules about confirmation, conflicts and what write tools can edit.

## Impact

- `knowledge/graph/queries.py`, `knowledge/flow/catalog.py` (and the executor that dispatches catalog methods), `actions/tools/documents.py`, `agent/prompts.py`, tests, `docs/`.
- Automated tests never spend. A real-model check of the prompt is optional, announced with an estimate, and needs a yes.

## Non-goals

- Editing `service.yaml` or other non-markdown files; new fields such as `product_owner` in the graph.
- A tool that reads raw documents (reading stays in `query_knowledge`).
- Making new documents searchable before the next ingestion run (existing limit).
- Any keyword routing or if/else in the agent: confirmation and conflict behavior is prompt guidance only.
