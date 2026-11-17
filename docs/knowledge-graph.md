# Knowledge graph

An in-memory graph of the ecosystem ("Demo Studio") built from the sample data. It answers **structural questions** (who owns what, who consumes which API, what belongs to which client) with plain data and no language model. It is part of the informational flow: the agent will reach it only through the single knowledge tool (`design-decisions.md` D5, D7), never through the MCP actions server.

Specification: `openspec/specs/knowledge-graph-queries/spec.md` once the change is archived, until then `openspec/changes/add-knowledge-graph/`.

## What is in the graph

| Entity | Comes from | Id example |
| --- | --- | --- |
| company, client, application | `company.yaml` | `client:demo-logistics` |
| service, team, person (tech lead), API, event | `repos/<service>/service.yaml` | `service:orders-service`, `api:payments-api`, `event:order.created` |
| epic, feature | `clients/<client>/product/features.yaml` | `feature:LOG-FEAT-102` |
| document (service docs and each client's vision) | the files themselves | `doc:orders-service/docs/api.md` |

Relations: `HAS_CLIENT`, `HAS_APPLICATION`, `HAS_SERVICE`, `OWNED_BY`, `LED_BY`, `PROVIDES`, `CONSUMES`, `PUBLISHES`, `SUBSCRIBES_TO`, `DOCUMENTED_BY`, `IMPLEMENTS`, `PART_OF` (feature to epic), `BELONGS_TO` (epic to client), `HAS_VISION`. An API is one entity per family (`payments-api`); the versions, with their status and sunset date, travel on the `PROVIDES` relation. A document has a `title` (its first heading) and a `status`: `obsolete` when its front matter says so (the actions server writes it), otherwise `current`.

Every entity and relation lists the files it came from (`sources`), and every answer lists the sources of the facts it reports, so a later answer can cite where a fact comes from.

## Questions it answers

| Method | Answers |
| --- | --- |
| `find_entities(text, type=None, limit=10)` | candidate entities for a loose name, best first |
| `client_overview(client)` | applications and services of a client, and its vision |
| `application_services(application)` | services of an application and its client |
| `service_owner(service)` | owning team and tech lead |
| `api_consumers(api)` | providers (with versions), consuming services with their application and client, deprecated versions |
| `event_flow(event)` | publishers and subscribers |
| `service_product_context(service)` | application, client, features with their epics, and the client's vision document |
| `relation_path(a, b)` | shortest chain of relations between two entities |
| `describe(entity)` | all relations of an entity, grouped |
| `obsolete_documents()` | documents marked obsolete, with service and path |

Names can be loose: any letter case, spaces, hyphens or underscores. When a name matches several entities, `find_entities` shows them all; the other methods take the best match of the type they need.

## Examples

Every example below is executed by `tests/knowledge/test_docs_examples.py`, and its output must match what is written here.

```python
from ecosystem_assistant.knowledge.graph import build_graph

graph = build_graph("data/ecosystem")
for candidate in graph.find_entities("payments")[:3]:
    print(candidate.id, candidate.match)
```

```text
service:payments-service partial
api:payments-api partial
team:payments-team partial
```

Who consumes an API, and where each answer comes from:

```python
result = graph.api_consumers("payments api")
for consumer in result.consumers:
    print(consumer.service.name, "in", consumer.application.name, "of", consumer.client.name)
print(result.sources)
```

```text
orders-service in Storefront of Demo Grocery
['company.yaml', 'repos/orders-service/service.yaml', 'repos/payments-service/service.yaml']
```

Ownership and event flow:

```python
owner = graph.service_owner("tracking-service")
print(owner.team.name, "/", owner.lead.name)
print([s.name for s in graph.event_flow("route.assigned").subscribers])
```

```text
tracking-team / Bruno Salas
['driver-service']
```

The product vision that applies to a service is the one of its own client:

```python
context = graph.service_product_context("driver-service")
print(context.client.name, context.vision.path)
print([f.feature.name for f in context.features])
```

```text
Demo Logistics clients/demo-logistics/product/vision.md
['Live vehicle positions', 'Automatic route assignment', 'Driver route notifications']
```

How two things are related (technical relations win over product ones when paths tie):

```python
path = graph.relation_path("tracking-service", "driver-service")
for step in path.steps:
    print(step.source.name, step.relation, step.direction, step.target.name)
```

```text
tracking-service PROVIDES out tracking-api
tracking-api CONSUMES in driver-service
```

A misspelled name is not an error; it comes back as a not-found result with the closest names first:

```python
missing = graph.service_owner("ordres-service")
print(missing.found, [s.name for s in missing.suggestions])
print(sorted(graph.service_owner("orders-service").to_dict()))
```

```text
False ['orders-service', 'driver-service', 'payments-service']
['found', 'lead', 'service', 'sources', 'team']
```

Results serialize to JSON with `to_dict()`. In the committed data nothing is obsolete yet:

```python
print(graph.obsolete_documents().documents)
```

```text
[]
```

## Rebuilding and its limits

- `build_graph(root)` reads a data root and returns a new graph; nothing is cached and nothing is written. To see a change (for example a document the actions server just marked obsolete), build again.
- It builds the **base** data. The simulated PRs under `prs/` are not applied: that is the job of the ingestion, which will point the builder at an updated root.
- A reference that does not resolve (an API nobody provides, an unknown feature, a missing document) stops the build with an error that names the file and the missing item.
- The graph is an index of declared facts. It does not read the prose of documents beyond the first heading and the front matter; searching document text is the job of the retrieval (RAG).
- Entity lookup is normalization and ranking, not understanding: it finds `Payments API`, not a paraphrase of it.
- When the graph outgrows memory or needs several writers, `design-decisions.md` D5 names the next step (Kùzu).
