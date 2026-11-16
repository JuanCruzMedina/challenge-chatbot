# Tasks

## 1. Project setup

- [x] 1.1 Ask the user's go-ahead for the first `uv` run (it downloads Python 3.12 to the user cache), then create `pyproject.toml` (package `ecosystem_assistant`, `mcp` pinned, `pytest` as dev dependency) and a local `.venv`; verify `uv run pytest --collect-only` runs with zero errors and `git status` shows `.venv` ignored.
- [x] 1.2 Add the package skeleton `src/ecosystem_assistant/actions/{__init__,server,workspace}.py` and `tools/__init__.py`, plus `var/` in `.gitignore`; verify `uv run python -c "import ecosystem_assistant.actions"` succeeds.
- [x] 1.3 Check the installed `mcp` SDK API (server class, tool decorator, in-memory client helper, error results) and record the confirmed names in a comment at the top of `server.py`; verify with a throwaway call that a tool listing and an `isError` result behave as `design.md` D-1 and D-7 assume.

## 2. Workspace, safe paths and audit log

- [x] 2.1 Write failing tests `tests/actions/test_workspace.py` for: slug and `doc_path` validation, rejection of `..`, absolute paths and non-`.md` files, rejection of a symlink escaping the workspace, atomic write leaving no partial file on a simulated failure, and one audit line per successful write; verify they fail for the right reason.
- [x] 2.2 Implement `workspace.py` (`DOCS_WORKSPACE` and `ACTIONS_AUDIT_FILE` settings, safe resolution, atomic write, audit append); verify the workspace tests pass.
- [x] 2.3 Write a failing test for `scripts/seed_workspace.py` (copies every sample repo into the workspace; running again leaves a fresh copy), implement the script, and verify the test passes and `data/ecosystem/` is unchanged.

## 3. Documentation tools

- [x] 3.1 Write failing tests `tests/actions/test_add_document.py` for the three scenarios of "Add a document" (created, existing not overwritten, unknown service and unsafe path rejected); verify they fail.
- [x] 3.2 Implement `add_document` in `tools/documents.py` with typed, constrained arguments and a routing-oriented description; verify its tests pass.
- [x] 3.3 Write failing tests `tests/actions/test_update_document.py` for the four scenarios of "Update a document with conflict detection" (updated, text not found, text not unique, missing document); verify they fail.
- [x] 3.4 Implement `update_document` (single exact occurrence, `conflict` outcome as a normal result, error result for a missing document); verify its tests pass.
- [x] 3.5 Write failing tests `tests/actions/test_mark_obsolete.py` for the three scenarios of "Mark a document as obsolete" (front matter written, idempotent, missing document rejected); verify they fail.
- [x] 3.6 Implement `mark_document_obsolete` (front-matter prepend, idempotent); verify its tests pass.
- [x] 3.7 Add a test that the committed sample data is untouched: checksum `data/ecosystem/` before and after successful, conflicting and failing calls of the three tools; verify it passes.

## 4. Server and discovery

- [x] 4.1 Write failing in-process MCP client tests `tests/actions/test_server_discovery.py` for the two "Tools are discoverable" scenarios (names present, non-empty descriptions, closed object schemas, `required` matches mandatory arguments) and for `isError` on invalid input versus a normal `conflict` result; verify they fail.
- [x] 4.2 Implement `server.py` (build the server, auto-discover modules in the tools package skipping `_`-prefixed ones, fail on import errors naming the module, `main()` over stdio); verify the discovery tests pass.
- [x] 4.3 Add a subprocess smoke test that starts the server over stdio with no network-related environment variables, lists tools and calls one; verify it passes and finishes in under 10 seconds.

## 5. Extensibility and isolation

- [x] 5.1 Write the extensibility test: copy a throwaway tool module into a temporary tools package, start the server on it, and assert the new tool is listed with its own schema and the default tools are unchanged; verify it passes without editing `server.py` or any default tool module.
- [x] 5.2 Write the broken-module test (an unimportable module makes startup fail naming that module); verify it passes.
- [x] 5.3 Write the architecture test that inspects the imports of `ecosystem_assistant.actions` and fails on retrieval, graph, agent or LLM-client imports; verify it passes now and fails when a forbidden import is temporarily added.

## 6. Documentation and integration

- [x] 6.1 Document the actions server in `docs/actions-server.md` (tools, schemas, conflict outcome, workspace and seeding, audit log, how to add a tool, how to run it over stdio, and that written documents are not searchable until ingestion); verify the documented seed and run commands work as written.
- [x] 6.2 Run the whole suite and `openspec validate add-mcp-actions-server --strict`; verify both are green and every `#### Scenario:` in the spec maps to at least one test (list the mapping in the closing report).
