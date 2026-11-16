# Tasks

## 1. Validator as a function (characterization first)

- [ ] 1.1 Add `pyyaml` to the dev dependency group (`pyproject.toml` and `uv.lock`, local venv only) and write characterization tests `tests/data/test_validate_current.py` that run the existing script on the committed data and assert: no errors, and `payments-api` v1 reported deprecated with `orders-service` as the affected consumer after PR-101; verify they pass against the current script before touching it.
- [ ] 1.2 Refactor `scripts/validate_data.py` into `validate(root)` returning `Result(errors, warnings, summary)` plus a thin `main()`, with existing checks moved over unchanged, and manifests collected in a list before indexing (design D-8); verify the characterization tests (now calling `validate()`) still pass and the command-line output for the current data is unchanged.

## 2. Hierarchy rules (on a synthetic fixture)

- [ ] 2.1 Write a test helper that builds a minimal valid hierarchical dataset in a temporary folder (company, two clients, three applications, services, visions, features, one simulated PR) and failing tests `tests/data/test_hierarchy_rules.py` for these scenarios: consistent manifest passes, unknown application, application of another client, duplicate service name, manifest name different from its folder, missing vision, feature pointing at another client's service, duplicate feature id, duplicate API id, PR manifest without client or application, summary lists clients with applications and services (assert on the output of `main()` with `capsys`), and `validate(root)` callable on a copy; verify they fail for the right reason.
- [ ] 2.2 Implement loading of `company.yaml` and the service checks (`client` and `application` present, known and consistent; manifest name equals folder; unique names), including the state-after-PR path; verify the related tests pass.
- [ ] 2.3 Implement the per-client checks (vision and feature catalog exist, features reference only services of the same client's applications), the company-wide id uniqueness checks (epics, features, APIs) and the hierarchy summary printed by `main()`; verify all rule tests pass.

## 3. Sample data

- [ ] 3.1 Write failing tests `tests/data/test_sample_hierarchy.py` on the committed data: one company, two clients, three applications, a client with two or more applications, the two visions differ, the four original service folders are present, the PR-101 manifest carries client and application, and `validate()` returns no errors; verify they fail.
- [ ] 3.2 Add `data/ecosystem/company.yaml` and `company/overview.md`, move `product/` with `git mv` to `clients/demo-grocery/product/` renaming `product-vision.md` to `vision.md`, and add `client` and `application` to the four existing manifests and to the PR-101 replacement manifest; verify with a grep that no reference to the old `data/ecosystem/product` path remains.
- [ ] 3.3 Add client `demo-logistics` with its own `product/vision.md` and `features.yaml` (ids prefixed `LOG-`), different in content from the grocery vision; verify the two files exist and the vision-differs test passes.
- [ ] 3.4 Add the two `fleet-tracker` services (`tracking-service`, `routing-service`) with `service.yaml`, README and one or two documents each, following design D-5; verify the files are consistent with the company file by running `validate()` and reading only the errors that mention the remaining service.
- [ ] 3.5 Add the `driver-app` service (`driver-service`) with `service.yaml`, README and one document; verify `validate()` returns no errors and the sample hierarchy tests pass.
- [ ] 3.6 Generalize the hard-coded list of four services in `tests/actions/test_seed_workspace.py` to read the sample folder; verify the whole existing suite still passes with seven services.

## 4. Documentation and integration

- [ ] 4.1 Update `data/ecosystem/README.md` (new layout, hierarchy, how to validate), `docs/design-decisions.md` D1 (company, clients and applications), and any path in `AGENTS.md` or `docs/` that mentions the old layout; verify with a grep that no stale path remains and the documented validate command runs as written.
- [ ] 4.2 Run the whole suite, the validator from the command line, and `openspec validate extend-ecosystem-hierarchy --strict`; verify all are green and every `#### Scenario:` in the spec maps to at least one test (list the mapping in the closing report).
