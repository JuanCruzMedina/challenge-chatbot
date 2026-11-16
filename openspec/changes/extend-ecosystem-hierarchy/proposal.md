# Proposal

## Why

The sample ecosystem is flat: one invented shop with four services and no company above it. The product vision is a company view: one company has several clients, each client several applications, and each client its own product vision. Without that structure the knowledge graph and the retrieval cannot answer cross-cutting questions ("which applications does each client have?", "whose product vision does this service serve?"). The data must exist, and be validated, before the graph is built.

## What Changes

- Add a company layer to the invented sample data: **1 company, 2 clients, 3 applications**.
  - Client `demo-grocery`: application `storefront` (the four existing services).
  - New client `demo-logistics`: applications `fleet-tracker` (two new services) and `driver-app` (one new service).
- Every `service.yaml` declares its `client` and `application`.
- Product vision becomes **per client**: the existing vision and features move under the client, and the new client gets its own, different vision and features.
- A company-level `company.yaml` lists clients and applications, and a short company overview document gives the portfolio view.
- Extend `scripts/validate_data.py` so the hierarchy is checked: unknown or mismatched client and application, a manifest name that differs from its folder, duplicate service names, duplicate epic, feature or API ids, missing visions, and features pointing at services of another client. The simulated PR's replacement manifest gets the same fields.
- The workspace layout `repos/<service>/` stays as it is, so the MCP Server and its seed script keep working unchanged.

Routing invariant restated (see `openspec/config.yaml`): this change only adds sample data and its validation; informational queries and actions are untouched.

## Capabilities

### New Capabilities
- `ecosystem-data-hierarchy`: the company, client and application structure of the sample data, the per-client product vision, and the validation rules that keep it consistent.

### Modified Capabilities
<!-- None: the MCP actions capability does not change. -->

## Impact

- `data/ecosystem/`: new `company.yaml`, `company/overview.md`, `clients/<client>/product/...`, three new service folders under `repos/`; the existing `product/` folder moves under `clients/demo-grocery/`; four existing manifests and the PR-101 replacement manifest gain two fields.
- `scripts/validate_data.py` is refactored into a testable function and extended; new tests under `tests/data/`.
- One existing test that hard-codes the four services is generalized.
- `pyyaml` joins the dev dependency group of the local venv (the validator already needs it). No LLM, no network.

## Non-goals

- Editing client or company documents (visions, overview) from the chat: the MCP tools address documents by service, so those documents are read-only for now. A later change can generalize the tools.
- Cross-client relations such as shared services.
- Ingestion, the knowledge graph or retrieval (later changes).
- Real organizations, people or products: everything stays invented.
