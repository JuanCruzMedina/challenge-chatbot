# Design

## Context

- The sample data (`data/ecosystem/`) holds four services, a flat product folder and one simulated PR; `scripts/validate_data.py` checks cross references. Behavior contract: `specs/ecosystem-data-hierarchy/spec.md`; motivation: `proposal.md`.
- The MCP actions server resolves documents as `<workspace>/repos/<service>/...`, and the seed script copies `data/ecosystem/repos/`. Both depend on the folder layout under `repos/` and on service names being unique, so the hierarchy must be metadata, not folders (see D-1).
- The validator will be the safety net for the future knowledge graph: it must be a function that tests can call on modified copies.

## Goals / Non-Goals

**Goals:**
- A hierarchy rich enough for company-wide questions, small enough to hand-check.
- Rules enforced by a validator that is itself tested.
- Zero change to the MCP server code and to existing service folders.

**Non-Goals:**
- Making client or company documents editable by the MCP tools.
- A generic schema language or a database for the sample data.

## Decisions

**D-1. Hierarchy as metadata, services stay flat.** `repos/<service>/` stays flat with globally unique names; each `service.yaml` gains `client` and `application`. Alternative: nest folders as `repos/<client>/<application>/<service>/`, which mirrors the hierarchy on disk but forces the MCP workspace, the seed script, `service` slugs and all tests to change. The flat layout keeps those untouched and the graph builder can read the hierarchy from the manifests.

**D-2. One `company.yaml` as the portfolio index.** It lists `company`, `clients` (id, name, `vision`, `features`) and `applications` (id, name, `client`). Services are not listed there; they point up with `client` and `application`, so each service stays self-describing and the file stays short. Alternative: list services in the company file too (two places to keep in sync).

**D-3. Vision and features per client under `clients/<client>/product/`.** The existing `product/` folder moves with `git mv` to `clients/demo-grocery/product/`, with `product-vision.md` renamed to `vision.md` so both clients use the same file names (`vision.md`, `features.yaml`). `demo-logistics` gets its own pair. Epic and feature ids are unique across the company: the new client's ids carry a prefix (`LOG-EPIC-…`, `LOG-FEAT-…`) and the existing grocery ids stay as they are; the validator enforces it (D-8).

**D-4. A company overview document.** `company/overview.md` is a short prose portfolio view (clients, applications, who owns what) so the retrieval has a company-level text to find, next to the structured graph facts.

**D-5. Second client's content.** `demo-logistics` is a fictional fleet and delivery business: applications `fleet-tracker` (services `tracking-service`, `routing-service`) and `driver-app` (service `driver-service`). Relations mirror the grocery shape but stay inside the client: `tracking-service` publishes `vehicle.position_updated`; `routing-service` subscribes to it and publishes `route.assigned`; `driver-service` subscribes to `route.assigned` and consumes `tracking-api`. Its vision is deliberately different (visibility and punctuality instead of checkout reliability).

**D-6. Validator as a function.** `validate_data.py` is split into `validate(root) -> Result(errors, warnings, summary)` plus a thin `main()`. Existing checks move over unchanged; hierarchy checks are added next to them. Tests build modified copies of the sample data in a temporary folder and assert on the returned errors, instead of parsing printed output.

**D-7. Names and ids.** Client ids are slugs (`demo-grocery`, `demo-logistics`); application ids are slugs unique across the company (`storefront`, `fleet-tracker`, `driver-app`). A service name is its folder name, and the validator checks that the manifest's `name` equals it, because the actions server uses the folder name as the `service` argument.

**D-8. Company-wide uniqueness and duplicate detection.** The current validator indexes services in a dictionary by name, so a second manifest with the same name silently replaces the first. Loading must collect manifests in a list first, report duplicates, and only then index. The same applies to epic ids, feature ids and API ids: with two clients, a repeated `EPIC-01` or `orders-api` would make references ambiguous, so the validator reports each duplicated id with the places that declare it. Cross-client use of an API is not forbidden by the validator (a real company could do it); the sample data simply has none.

**D-9. Simulated PRs are held to the same rules.** A PR's `files/service.yaml` replaces the whole manifest, so it must carry `client` and `application` too, and the state-after-PR check runs the same hierarchy rules as the base data.

## Risks / Trade-offs

- **Hand-written data drifts** → the validator is the guard and runs in the final task; tests cover each rule with a minimal mutation.
- **Moving `product/` breaks references** → search for the old paths (`data/ecosystem/README.md`, the validator, `docs/`) in the move task and verify with a grep that none remain.
- **A hard-coded list of four services in an existing test** → generalize it to read the sample folder (task 2.5).
- **Client and company documents cannot be edited from the chat yet** → stated as a non-goal; the MCP `service` argument would need generalizing in a later change.
- **Second client adds data volume** → kept to three small services with one or two documents each.
- **The PR replacement manifest is easy to forget when the schema grows** → the "after PR" check goes through the same rules, and a test builds a PR whose manifest lacks the new fields.
