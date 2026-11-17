# Design

## Context

- The data (`data/ecosystem/`) is validated by `scripts/validate_data.py`: company file, service manifests, per-client product catalogs, documents, and simulated PRs. Behavior contract: `specs/knowledge-graph-queries/spec.md`; motivation: `proposal.md`.
- Decision D5 (`docs/design-decisions.md`): NetworkX in memory, accessed only through our own query interface, with Kùzu as the future option. This change implements that interface.
- The existing architecture test forbids the actions package from importing `ecosystem_assistant.knowledge`, so the graph lives under that name and cannot be reached from the actions side. The retrieval (RAG) will sit next to it as `ecosystem_assistant.knowledge.retrieval` in a later change.
- The agent will see this graph only through one knowledge tool (D7); how a language model chooses which query to run is the next change's problem, so the interface here is plain functions with typed, serializable results.

## Goals / Non-Goals

**Goals:**
- A small, readable graph model that mirrors the data and can answer the questions in the spec.
- Every fact traceable to a source file, so later answers can cite it.
- Query functions that are easy for a language model to be given as tools later: few, named by intent, with simple arguments.

**Non-Goals:**
- Persistence, incremental updates, performance work, a query language.
- Any use of a language model, and any network access.

## Decisions

**D-1. NetworkX `MultiDiGraph` behind a `KnowledgeGraph` class.** Nodes are keyed `"<type>:<id>"` (for example `service:orders-service`, `api:payments-api`, `event:order.created`, `doc:orders-service/docs/api.md`) with attributes `type`, `name` and `sources`. Edges are keyed by relation name and carry `sources`. A multigraph is needed because two entities can be related in more than one way. Nothing outside the package touches NetworkX (D5).

**D-2. Relation vocabulary (fixed and small).** `HAS_CLIENT`, `HAS_APPLICATION`, `HAS_SERVICE`, `OWNED_BY`, `LED_BY`, `PROVIDES`, `CONSUMES`, `PUBLISHES`, `SUBSCRIBES_TO`, `DOCUMENTED_BY`, `IMPLEMENTS`, `PART_OF` (feature to epic), `BELONGS_TO` (epic to client), `HAS_VISION`. The vocabulary is a module constant so tests and later tools share it.

**D-3. APIs as families with versions on the edge.** Manifests say `consumes_apis: [payments-api]` without a version and `provides_apis` with versions. So one `api:payments-api` node exists; the `PROVIDES` edge carries the list of versions with their status and sunset date. A deprecated version is therefore visible when asking for consumers (the spec's deprecation scenario) without version nodes.

**D-4. Documents as nodes, with status and title.** Each manifest `docs` entry becomes `doc:<service>/<path>`; client vision documents become `doc:clients/<client>/product/vision.md` linked by `HAS_VISION`. The builder reads the file: the first `# ` heading is the title and a YAML front matter `status: obsolete` (written by the actions server) sets `status: obsolete`; otherwise `current`. This closes the loop with the actions server: after a document is marked obsolete and the graph rebuilt, the graph knows. Company overview and ADR files that no manifest lists are not entities.

**D-5. A builder that fails loudly.** `build_graph(root)` reads the YAML files directly, without importing the validator script (scripts are not a package, and the validator belongs to the data tooling). A reference to an API, feature, service or file that does not resolve raises `GraphBuildError` naming the file and the missing item. The validator accepts the same data, which a test checks on the committed data and on the synthetic dataset helper from `tests/data`, so the two cannot drift silently.

**D-6. Provenance on everything.** Each node and edge stores `sources`, a sorted list of data-root-relative file paths (a service node: its `service.yaml`; a `CONSUMES` edge: the consumer's `service.yaml`; a feature: its client's `features.yaml`). Query results include the union of the sources of the facts they report.

**D-7. Query interface: a `KnowledgeGraph` method per question, results as small dataclasses with `to_dict()`.** Methods: `find_entities(text, type=None, limit=10)`, `describe(entity)`, `client_overview(client)`, `application_services(application)`, `api_consumers(api)`, `service_owner(service)`, `event_flow(event)`, `service_product_context(service)`, `relation_path(a, b)`, `obsolete_documents()`. Each takes plain strings and resolves them with `find_entities` when they are not exact ids, so a language model can pass what the user said. An unresolvable entity returns `NotFound(query, suggestions)` instead of raising.

**D-8. Entity resolution is normalization plus ranking.** Text is lowercased and split into alphanumeric tokens (`Payments API`, `payments-api`, `payments_api` all become `payments api`). Ranking: exact id or name, then all query tokens equal to the entity's tokens, then all query tokens contained in the entity's tokens, then substring. Ties are ordered by type (service, api, event, ...) then name. This is deterministic and is not routing: it only finds entities.

**D-9. Path as a readable chain.** `relation_path(a, b)` runs the shortest path on the undirected view of the graph and returns steps `(entity, relation, direction, next_entity)`. Hierarchy-only paths through the company node are excluded by ignoring `HAS_CLIENT`, so two unrelated services do not look connected merely because they belong to the same company; the result is empty when no other connection exists. When two paths have the same length, the one through technical relations (`PROVIDES`, `CONSUMES`, `PUBLISHES`, `SUBSCRIBES_TO`) wins over one through product or hierarchy relations, so `tracking-service` and `driver-service` are connected through `tracking-api` rather than through the feature they both implement.

**D-10. Base state only.** The builder takes a data root and reads `repos/`, `clients/` and `company.yaml`. Simulated PRs under `prs/` are not applied: that is ingestion's job, which will build a graph from an updated root.

## Risks / Trade-offs

- **Builder and validator drift** → shared-dataset tests (D-5) and the validator remaining the gate for the data.
- **Entity resolution picks the wrong candidate** → ranking is deterministic and returns several candidates; the later informational graph shows ambiguity to the user instead of guessing.
- **A fixed relation vocabulary limits new questions** → adding a relation is a small, local change; the vocabulary is one constant.
- **Rebuilding on every change does not scale** → irrelevant at this size; the interface (`build_graph(root)`) leaves room for incremental updates.
- **Reading documents for title and status couples the builder to the file layout** → it reads only the first heading and the front matter, and a missing file is a build error, not a silent gap.
