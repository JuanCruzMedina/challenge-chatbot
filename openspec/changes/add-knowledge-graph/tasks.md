# Tasks

## 1. Setup

- [ ] 1.1 Add `networkx` as a runtime dependency (pinned with `~=`) and move `pyyaml` from the dev group to the runtime dependencies, using `uv` in the local venv only; create the package skeleton `src/ecosystem_assistant/knowledge/__init__.py` and `knowledge/graph/{__init__,model,build,queries}.py` with docstrings only; verify `uv run python -c "import ecosystem_assistant.knowledge.graph, networkx, yaml"` succeeds and the existing suite still passes.

## 2. Building the graph

- [ ] 2.1 Write failing tests `tests/knowledge/test_build_hierarchy.py` on the synthetic dataset helper and on the committed data for "The hierarchy is represented" (counts of clients, applications and services, each service linked to exactly one application); verify they fail.
- [ ] 2.2 Implement `model.py` (node keys, entity types, relation vocabulary constants) and the hierarchy part of `build.py` (`build_graph(root)`, `GraphBuildError`); verify the hierarchy tests pass.
- [ ] 2.3 Write failing tests `tests/knowledge/test_build_services.py` for "Service manifests become entities and relations" (team, lead, provides, consumes, publishes, subscribes, with API versions on the `PROVIDES` edge); then implement that part of the builder; verify they pass.
- [ ] 2.4 Write failing tests `tests/knowledge/test_build_product_and_docs.py` for "Product data becomes entities and relations" and "Documents carry their title and status" (feature to epic to client, feature to services, client to vision, front matter `obsolete`, first-heading title); then implement them; verify they pass.
- [ ] 2.5 Write failing tests `tests/knowledge/test_build_guarantees.py` for provenance (every entity and relation lists existing source files), determinism (two builds identical) and the dangling-reference failure naming the file and the missing item; then implement them; verify they pass and the validator and the builder both accept the committed data.

## 3. Queries

- [ ] 3.1 Write failing tests `tests/knowledge/test_find_entities.py` for the four "Entities can be found by name" scenarios (exact, loose wording, ambiguous, unknown); then implement `find_entities` and the normalization and ranking of design D-8 in `queries.py`; verify they pass.
- [ ] 3.2 Write failing tests `tests/knowledge/test_queries_structure.py` for client overview, application services, service owner and `describe`; then implement them; verify they pass.
- [ ] 3.3 Write failing tests `tests/knowledge/test_queries_dependencies.py` for API consumers (including the deprecated-version scenario on a modified copy) and event flow; then implement them; verify they pass.
- [ ] 3.4 Write failing tests `tests/knowledge/test_queries_product_and_paths.py` for the product context of a service (features, epics, the right client's vision), the relation path (including no path, and that the company node is not a connection), and obsolete documents on a modified copy; then implement them; verify they pass.
- [ ] 3.5 Write failing tests `tests/knowledge/test_results.py` for plain-data results (JSON serialization, sources listed) and the not-found result with suggestions for a misspelled entity in every query that takes an entity; then implement `NotFound` and `to_dict()` on all results; verify they pass.

## 4. Isolation, documentation and integration

- [ ] 4.1 Write `tests/knowledge/test_isolation.py`: the graph package has no imports of the actions package, the agent, LLM clients or network libraries (with a check that the detector flags a synthetic offender), and building the graph and running every query leaves a checksum of the data root unchanged; verify it passes.
- [ ] 4.2 Document the graph in `docs/knowledge-graph.md` (entities, relations, the query methods with an example each, provenance, how to rebuild from another root, limits) and update `docs/design-decisions.md` D5 to point to it; verify that every example in the document runs as written.
- [ ] 4.3 Run the whole suite, the data validator and `openspec validate add-knowledge-graph --strict`; verify all are green and every `#### Scenario:` in the spec maps to at least one test (list the mapping in the closing report).
