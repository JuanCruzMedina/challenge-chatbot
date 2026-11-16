# Sample ecosystem: "Demo Studio"

**Everything in this folder is invented.** The company, clients, teams, people, services, APIs, URLs and dates are fictional and do not represent any real organization or person.

## Structure

```text
company.yaml                      the company, its clients and their applications
company/overview.md               portfolio view in prose (clients, applications, services)
clients/<client>/product/         the client's product vision (vision.md) and feature catalog (features.yaml)
repos/<service>/                  one folder per service: service.yaml, README.md and docs/
prs/<pr>/                         simulated PRs used to test incremental ingestion
```

| Client | Application | Services |
|---|---|---|
| Demo Grocery | Storefront | `catalog-service`, `orders-service`, `payments-service`, `notifications-service` |
| Demo Logistics | Fleet Tracker | `tracking-service`, `routing-service` |
| Demo Logistics | Driver App | `driver-service` |

Each client has its own, different product vision.

## How the pieces relate

- A **service** declares in its `service.yaml` the `client` and `application` it belongs to, its owner, the APIs it provides and consumes, the events it publishes and subscribes to, its docs, and the features it implements. Those relations feed the Knowledge Graph; the text of the `.md` files feeds the RAG.
- A **feature** belongs to an epic of one client and lists the services that implement it. It may only list services of its own client.
- Service folders stay **flat** under `repos/` with unique names: the folder name is what the MCP actions server uses as `service`. The hierarchy lives in the manifests, not in the folder tree.
- Epic, feature and API ids are unique across the whole company (the second client's ids start with `LOG-`).
- A **simulated PR** (`prs/pr-101-payments-api-v2/`) replaces a whole manifest and adds a document. Its manifest carries `client` and `application` like any other.

## Validate

```bash
uv run python scripts/validate_data.py          # prints the hierarchy, then OK or the errors
uv run python scripts/validate_data.py <root>   # same, on another copy of the data
```

It checks the hierarchy (known client and application, manifest name equal to its folder, unique names and ids), each client's vision and feature catalog, the references between services (APIs, events, docs, features) and the state of the data after every simulated PR.
