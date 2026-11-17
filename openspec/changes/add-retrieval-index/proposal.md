# Proposal

## Why

The Knowledge Graph answers structural questions, but most questions about documentation are about content: what a runbook says when a vehicle disappears from the map, what a client's product vision prioritizes. That needs retrieval over the text of the documents. The challenge asks for RAG next to the graph, and the informational flow will combine both later. The index must also stay current as documents change (from the chat or a PR), so it updates incrementally, file by file.

## What Changes

- Add a retrieval index over the ecosystem's markdown documents (service documents, client visions, the company overview), split into section chunks that keep their title, heading path, file, service, application, client, status and content hash.
- Add a search that returns the best chunks for a question with their score and a citation, and can be restricted to a client, application or service. Obsolete documents are left out unless asked for.
- Add a `sync` that compares the files with the index by content hash and re-embeds only what changed: new files (for example one created through the actions server), edited, obsolete and deleted files. The ingestion will call it later.
- Use a local vector store (Chroma, persisted under `var/index/`) and local embeddings behind a small interface: MiniLM through Chroma's ONNX runtime (no PyTorch) and an offline hashing embedder for the tests. The index remembers which embedder built it.
- Add a small evaluation set of questions with the document each should find, and a script that reports how often it is in the top results.
- Telemetry is off, nothing is downloaded without an explicit opt-in, and no LLM is called.

Routing invariant restated (see `openspec/config.yaml`): this index belongs to the informational flow; the agent will reach it only through the single knowledge tool, never through the MCP actions server.

## Capabilities

### New Capabilities
- `knowledge-retrieval-index`: chunking and metadata, the incremental index, search with filters and citations, embedder handling, retrieval evaluation, and isolation.

### Modified Capabilities
<!-- None. -->

## Impact

- New package `ecosystem_assistant.knowledge.retrieval`, tests under `tests/retrieval/`, a script `scripts/eval_retrieval.py`.
- New runtime dependency `chromadb` (pinned, local venv only; it brings its ONNX runtime, a few hundred MB). The first real embedding downloads the MiniLM model (about 80 MB) into the user cache, only after an explicit opt-in.
- `var/index/` (git-ignored). No change to the data, the graph or the actions server.

## Non-goals

- Generating answers with a language model, and combining retrieval with the graph (the next change).
- Reranking, keyword hybrid search, query rewriting, other languages.
- Triggering the sync from a PR or a schedule (the ingestion change); the sync is called by hand here.
- Showing the graph's facts inside search results.
- Making documents added through the actions server known to the graph: it reads only the documents each manifest lists, so such a document is searchable here but invisible to the graph. Recorded for the ingestion change.
