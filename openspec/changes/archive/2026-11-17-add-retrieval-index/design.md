# Design

## Context

- The documents are small: 22 markdown files (median 751 characters, longest section 691), so about 60 chunks in total. Behavior contract: `specs/knowledge-retrieval-index/spec.md`; motivation: `proposal.md`.
- Decision D4 (`docs/design-decisions.md`) chose local Chroma and local embeddings. It named `sentence-transformers`; this change revises that (D-2) because that library pulls in PyTorch, which is heavy for a demo.
- The knowledge graph (`ecosystem_assistant.knowledge.graph`) already knows which application and client each service belongs to. Retrieval reuses it for that metadata instead of parsing manifests a second time.
- The actions server can create or edit documents, and the graph only knows the documents listed in manifests. Retrieval therefore scans the folders on disk; that is why a document added from the chat is searchable here.
- Tests must not use the network or download models, so embeddings go through an interface with an offline deterministic implementation.

## Goals / Non-Goals

**Goals:**
- A small index that stays in step with the files by itself, re-embedding only what changed.
- Every hit is citable: file, title, heading path, scope.
- Quality is measured, not assumed.
- No surprise network use, no telemetry.

**Non-Goals:**
- Answer generation, reranking, hybrid keyword search, multilingual support.
- Triggering the sync automatically.

## Decisions

**D-1. Chroma persistent client, vectors supplied by us.** The collection is created without an embedding function and every call passes the embeddings we computed, so the embedder is ours and testable. Cosine distance. Settings turn anonymized telemetry off. The index lives in `VECTOR_INDEX_DIR` (default `var/index/`, git-ignored). The exact Chroma API is verified against the installed version before use (task 1.2).

**D-2. Embeddings: MiniLM through Chroma's ONNX runtime, not `sentence-transformers`.** The `all-MiniLM-L6-v2` model runs on ONNX, which `chromadb` already depends on, so no PyTorch is installed (hundreds of MB saved, simpler install). Alternatives: `sentence-transformers` (more models, but PyTorch), `fastembed` (also ONNX, another dependency), an embeddings API (data leaves the machine, costs money). The model is English-only, which fits the English documents.

**D-3. An `Embedder` interface with two implementations.** `name` and `embed(texts) -> vectors`. `HashingEmbedder`: signed feature hashing of lowercase word unigrams and bigrams into 256 dimensions, L2-normalized, using a stable hash (not Python's randomized `hash`), so results repeat across runs and machines. It is lexical, weak on paraphrase, and exists for tests and offline use. `MiniLMEmbedder`: wraps Chroma's ONNX MiniLM; it first checks that the model is cached and otherwise fails with a message naming `ALLOW_MODEL_DOWNLOAD=1`, the opt-in. The selection is by name (`hashing`, `minilm`) from an environment variable with `minilm` as default.

**D-4. Chunking by section.** The front matter is read for the status (and removed from the text). The body is split at ATX headings (`#` to `######`), ignoring `#` lines inside fenced code. Each chunk is the heading path (`Title > Section`) followed by the section text; that string is what gets embedded and what a result shows. A section longer than 1200 characters is grouped by paragraphs up to that size; a single longer paragraph stays whole. Chunk ids are `<relative path>#<n>`, so they are deterministic.

**D-5. Metadata from the path and the graph.** The scope comes from the path: `repos/<service>/...` is a service document, `clients/<client>/product/...` a client document, `company/...` a company document. For a service document, application and client come from `graph.service_product_context(service)`; an unknown service gets empty values instead of failing, so a new folder is still indexed. The status comes from the document's own front matter, read from the file, not from the graph, so a document the graph does not know still has the right status. The dependency goes one way: retrieval imports the graph, never the reverse (a test enforces it).

**D-6. Incremental sync by version.** Each chunk stores `version = sha256(file hash + service + application + client)`. A sync scans the files, reads the stored `path -> version` map from the index, and: adds paths not in the index, replaces (delete by path, then add) paths whose version differs, deletes paths no longer on disk, and does nothing for equal versions. Including the graph-derived context in the version means moving a service to another application is noticed even though no file changed. The report is `added / updated / removed / unchanged` file counts plus the number of chunks embedded, which the tests use to prove that nothing is re-embedded needlessly.

**D-7. Search.** The question is embedded, Chroma is queried with a `where` filter (client, application, service, and `status = current` unless obsolete documents are requested), and the cosine distance becomes a similarity score in `[0, 1]`. `k` is clamped to `[0, 20]` with a default of 5; an empty question returns an empty list. Ties are broken by chunk id so results are deterministic. Hiding obsolete documents by default is deliberate (an obsolete document should stop being presented as current); callers who need the history can ask for it.

**D-8. The index remembers its embedder.** The collection metadata stores the embedder name and vector size. Opening an index with a different embedder raises `IndexMismatchError` naming both and saying to rebuild; it never mixes vector spaces.

**D-9. Evaluation set and script.** `evaluation/retrieval.yaml` lists questions with the expected document path(s). `scripts/eval_retrieval.py` builds or opens an index on a chosen data root and embedder, runs each question for the top `k` (default 3), prints hit or miss with the rank of the first expected document, and the overall hit rate; `--min-hit-rate` makes it exit non-zero below that value. The hashing embedder runs in the automated tests; a run with real embeddings is manual, needs the opt-in, and its numbers go into the documentation. With about fifteen questions the result is an indicator, not a statistic.

**D-10. Sync is a function, not a service.** `RetrievalIndex.sync(root, graph=None)` builds the graph itself when none is given. The ingestion change will call it; here it is called by hand or by the script.

## Risks / Trade-offs

- **Chroma API drift** → pin the version and verify the API first (task 1.2).
- **Hashing embedder is weak on paraphrases** → it is for tests and offline use; quality claims come only from the real embedder's evaluation.
- **Hiding obsolete documents can hide the only description of an old behavior** → documented; `include_obsolete` exists; the informational flow decides whether to ask for it.
- **Graph-derived metadata can go stale between syncs** → covered by the version (D-6); syncing is cheap.
- **A small evaluation set** → reported as an indicator; questions are written from the documents' content, not tuned to the embedder.
- **Chroma's dependency weight and the MiniLM download** → local venv and user cache only, the download needs an explicit opt-in, and both are announced to the user first.
