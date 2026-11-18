# Proposal

## Why

The graph knows only the documents a hand-written manifest lists, and only as documents of a service. A document created from the chat is searchable but invisible to the graph, and nothing says what a document is about. The pull request review finds the documentation of a change only by text search, which loses documents (the retries rule was missed when the question was in Spanish and the document in English). The product direction is that the model connects the information: documents say what they are about, and the graph can answer "which documents talk about X".

This is the first of two changes. This one is the graph side (reading and querying links); the second one makes the chat write them.

## What Changes

- A markdown document of a service may declare `about:` in its front matter: a list of names of services, APIs or events (a single name is accepted too).
- The graph reads every markdown document under `repos/<service>/` that has `about`, not only the manifest ones. The document is linked to its service (`DOCUMENTED_BY`) and to each entity it names with a new relation `ABOUT` (document to entity).
- A name that matches no entity does not fail the build: it is kept in `unresolved_links` (document and name) so it can be reported and corrected.
- New query `documents_about(entity)`: the documents about an entity, with their service, path, title and status, and how each is linked (`about`, or `documented_by` for the manifest documents of a service). It is in the plan catalog. `describe` shows the new relation with no change.

## Capabilities

### Modified Capabilities
- `knowledge-graph-queries`.

## Impact

- `knowledge/graph/{model,build,queries}.py`, `knowledge/flow/catalog.py`, tests, `docs/knowledge-graph.md`, `docs/informational-flow.md`. Tests use temporary copies of the sample data; the sample data does not change.

## Non-goals

- Writing links from the chat (the next change).
- Links between documents (`[[other-document]]`) and backlinks.
- Features or other entity types in `about` (services, APIs and events only).
- Filtering the retrieval index by link.
