# Tasks

## 1. Setup and API check

- [ ] 1.1 Ask the user's go-ahead to add `chromadb` (a few hundred MB in the local venv, no global install), add it with `uv` pinned with `~=`, and create the package skeleton `src/ecosystem_assistant/knowledge/retrieval/{__init__,chunking,embedders,index,search}.py` (docstrings only) and `tests/retrieval/`; verify `uv run python -c "import chromadb, ecosystem_assistant.knowledge.retrieval"` succeeds and the existing suite still passes.
- [ ] 1.2 Check the installed `chromadb` API with a throwaway script outside the repo, using a temporary folder and hand-made vectors only (no model download): persistent client and the setting that disables telemetry, creating a collection with cosine distance and metadata, `add`, `get` with `include`, `query` with a `where` filter combining conditions, `delete` by `where`, and the ONNX MiniLM class with the location of its cache; record the confirmed names in a comment at the top of `index.py`; verify nothing was downloaded.

## 2. Chunking and metadata

- [ ] 2.1 Write failing tests `tests/retrieval/test_chunking.py` for: one chunk per section with the heading path, a single-section document is one chunk, a long section split at paragraph boundaries (none over 1200 characters except one longer paragraph, none cut in the middle), `#` inside fenced code is not a heading, front matter removed from the text and its status read, and deterministic chunk ids and texts; verify they fail.
- [ ] 2.2 Implement `chunking.py` (front matter, headings, paragraph grouping, chunk ids, content hash); verify the chunking tests pass.
- [ ] 2.3 Write failing tests `tests/retrieval/test_documents.py` for the intended files only (repos, client product and company folders; not `prs/`, not hidden or temporary files), the scope of each file, and the metadata of chunks (service, application and client from the graph; client documents with a client and no service; the company overview with neither; an unknown service folder with empty application and client); then implement the document discovery and metadata in `chunking.py`; verify they pass on the synthetic dataset and on the committed data.

## 3. Embedders

- [ ] 3.1 Write failing tests `tests/retrieval/test_embedders.py` for the hashing embedder (equal vectors for equal text across calls, unit length, two payment-retry texts closer to each other than to a vehicle-tracking text, no network and no files used); then implement `HashingEmbedder` and the `Embedder` interface in `embedders.py`; verify they pass.
- [ ] 3.2 Write failing tests for `MiniLMEmbedder` creation that never touch the network: with the model not cached and no opt-in it fails naming `ALLOW_MODEL_DOWNLOAD=1` and downloads nothing; with the model reported as cached it is created; embedder selection by name and an unknown name is rejected; then implement them; verify they pass.

## 4. Index and sync

- [ ] 4.1 Write failing tests `tests/retrieval/test_index_store.py` for: creating and reopening an index, refusing a different embedder with an error naming both and saying to rebuild, telemetry disabled in the client settings, and the index folder being configurable and outside the data root; then implement `RetrievalIndex` (open, embedder pin, telemetry off) in `index.py`; verify they pass.
- [ ] 4.2 Write failing tests `tests/retrieval/test_sync.py` for the six sync scenarios (first sync adds all, second changes nothing and embeds nothing, an edited file is re-embedded alone and the old text is gone, a new file becomes searchable with the right service and client, a deleted file leaves the index, a document marked obsolete through the actions server changes status), using a counting embedder to prove what was embedded; then implement `sync` with the version of design D-6 and the report; verify they pass.

## 5. Search

- [ ] 5.1 Write failing tests `tests/retrieval/test_search.py` for: a question finds the document that answers it, filters by client, application and service, obsolete hidden by default and shown on request, `k` clamped to 0 to 20 with the default of 5, empty question gives no results, deterministic ordering of ties, and JSON-serializable results with the citation fields; then implement `search.py` and wire it to the index; verify they pass.

## 6. Evaluation

- [ ] 6.1 Write `evaluation/retrieval.yaml` with about fifteen questions, written from the content of the documents (a mix of API, runbook, ADR, product vision and company questions, some that exist in both clients), each with its expected document path(s), and a test that every expected path exists under the sample data; verify it passes.
- [ ] 6.2 Write failing tests `tests/retrieval/test_eval_script.py` for the report (one line per question with hit or miss and rank, then the overall rate) and for the non-zero exit when the rate is below `--min-hit-rate`; then implement `scripts/eval_retrieval.py`; verify they pass, run it once with the hashing embedder, and record the measured hit rate in the documentation.
- [ ] 6.3 Ask the user's go-ahead for the first real embedding (it downloads the MiniLM model, about 80 MB, into the user cache and needs `ALLOW_MODEL_DOWNLOAD=1`), then run the evaluation once with the MiniLM embedder; verify it completes offline afterwards, and record the measured hit rate next to the hashing one.

## 7. Isolation, documentation and integration

- [ ] 7.1 Write `tests/retrieval/test_isolation.py`: the retrieval package has no imports of the actions package, the agent, LLM clients or network libraries (with a check that the detector flags a synthetic offender), the graph package does not import retrieval, and building, syncing and searching leave a checksum of the data root unchanged; verify it passes.
- [ ] 7.2 Document the index in `docs/retrieval-index.md` (what is indexed, chunking, metadata, sync and its report, search and filters, embedders and the opt-in, evaluation and the measured numbers, limits), with worked examples that a test runs and compares like the graph's document, and update `docs/design-decisions.md` D4 for the embedding choice; verify every example runs as written.
- [ ] 7.3 Run the whole suite, the data validator and `openspec validate add-retrieval-index --strict`; verify all are green and every `#### Scenario:` in the spec maps to at least one test (list the mapping in the closing report).
