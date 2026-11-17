# Proposal

## Why

The informational flow must answer questions about structured facts and the relations between entities: who owns a service, who consumes an API, what a deprecation affects, which client's product vision a service serves. A vector search alone cannot answer those reliably. The challenge asks for a Knowledge Graph next to the RAG, and the sample data now has the shape (company, clients, applications, services, features) that makes it worthwhile. The graph needs no model and no network, so it is built first, and the RAG and the agent will use it later.

## What Changes

- Add an in-memory Knowledge Graph, built from the sample ecosystem data (company file, service manifests, client product catalogs, document files). It holds companies, clients, applications, services, teams, people, APIs, events, epics, features and documents, with the relations between them.
- Every entity and relation records the source file it came from, so answers can cite where a fact comes from.
- Documents carry their status: a document marked obsolete by the actions server (front matter) shows as obsolete after the graph is rebuilt.
- Add a query interface that answers structural questions with plain, JSON-serializable data: find an entity by loose name, describe it, list the applications and services of a client, the consumers of an API, the owner and lead of a service, the publishers and subscribers of an event, the features of a service and the product vision of its client, the shortest relation path between two entities, and the obsolete documents.
- The graph is rebuilt from a data root, so ingestion can later point it at updated data. It is never persisted.
- The graph code does not depend on the actions server, the agent, any LLM client or the network, and never writes to the data.

Routing invariant restated (see `openspec/config.yaml`): this graph belongs to the informational flow; it is later exposed to the agent only through the single knowledge tool, never through the MCP actions server.

## Capabilities

### New Capabilities
- `knowledge-graph-queries`: building the ecosystem graph from the data, finding entities, answering structural questions, provenance, and isolation.

### Modified Capabilities
<!-- None. -->

## Impact

- New package `ecosystem_assistant.knowledge.graph` and tests under `tests/knowledge/`.
- New runtime dependency `networkx` (pinned, local venv only); `pyyaml` moves from the dev group to the runtime dependencies because the builder reads YAML.
- No change to `data/ecosystem/`, the actions server or the validator. No LLM, no network.

## Non-goals

- Retrieval over document text (the RAG) and the informational graph that combines both (later changes).
- Text-to-query translation or any LLM use: the interface is plain functions.
- Incremental updates, persistence, or applying simulated PRs: the graph is rebuilt from a data root, and ingestion decides which root.
- A graph database, a query language, or any performance work: the data is tiny.
- Parsing source code or document prose into entities.
