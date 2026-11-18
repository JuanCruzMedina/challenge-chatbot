# Proposal

## Why

A graph answer is cut at 1,500 characters before the model sees it. While fixing the "all teams and their leads" question we measured the whole catalog on the sample data: `describe` of a service (2,195 characters) and the list of documents (2,376) already exceed the cap and are cut without a trace. A cut list looks like a complete one, so the model may say that data does not exist.

## What Changes

- The cap per graph answer goes from 1,500 to 3,000 characters and the total evidence from 9,000 to 12,000, so the two known cases fit.
- A fact that was cut is marked (`truncated`) and the flow's trace records it, so it can be seen in any trace or report.
- A test runs every catalog query on the sample data with a representative argument, requires that none is cut, and fails when a query is added to the catalog without a case, so a new query that returns long lists must be made compact before it ships.

## Capabilities

### Modified Capabilities
- `knowledge-flow-answers`.

## Impact

- `knowledge/flow/evidence.py`, `knowledge/flow/nodes.py`, tests, `docs/informational-flow.md`. Larger facts use more input tokens, only when the graph answer is large.

## Non-goals

- Compacting every query's format (only `teams_overview` was compacted).
- Paginating results.
- Changing the passages' own cap (1,500 characters).
