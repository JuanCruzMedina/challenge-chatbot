"""Retrieval index on a local Chroma collection (design.md D-1, D-6, D-8).

chromadb 1.5.9 API, confirmed with a throwaway probe (task 1.2):
- Client: ``chromadb.PersistentClient(path=..., settings=Settings(anonymized_telemetry=False))``;
  ``client.get_settings().anonymized_telemetry`` reads the setting back.
- Collection: ``client.create_collection(name, configuration={"hnsw": {"space": "cosine"}},
  metadata={...}, embedding_function=None)``; our metadata survives a reopen with
  ``client.get_collection(name, embedding_function=None)``. We always pass our own embeddings.
- ``col.add(ids, embeddings, documents, metadatas)``, ``col.get(include=["metadatas"])``,
  ``col.delete(where={...})``, ``col.query(query_embeddings, n_results, where, include=[...])``.
- Filters combine with ``{"$and": [{"client": "c1"}, {"status": "current"}]}``; a filter that
  matches nothing returns ``[[]]`` instead of raising. Cosine distance is ``1 - similarity``.
- MiniLM: ``chromadb.utils.embedding_functions.ONNXMiniLM_L6_V2``. Constructing it downloads
  nothing; the download happens on the first embedding. The model is cached when the six files
  ``config.json, model.onnx, special_tokens_map.json, tokenizer_config.json, tokenizer.json,
  vocab.txt`` exist under ``DOWNLOAD_PATH / "onnx"``
  (``~/.cache/chroma/onnx_models/all-MiniLM-L6-v2``).
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from ecosystem_assistant.knowledge.graph.build import build_graph
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from ecosystem_assistant.knowledge.retrieval.documents import ServiceContext, discover_documents, load_chunks
from ecosystem_assistant.knowledge.retrieval.embedders import Embedder
from ecosystem_assistant.knowledge.retrieval.search import DEFAULT_RESULTS, Hit, run_search

COLLECTION = "documents"
# src/ecosystem_assistant/knowledge/retrieval/index.py -> repository root
REPO_ROOT = Path(__file__).resolve().parents[4]


class IndexMismatchError(RuntimeError):
    """The index was built with another embedder; mixing vector spaces would give wrong results."""


@dataclass(frozen=True)
class SyncReport:
    added: int           # files that were not in the index
    updated: int         # files whose version changed (content or graph context)
    removed: int         # files that disappeared from disk
    unchanged: int       # files already up to date
    empty: int           # files without text of their own: nothing to index
    chunks_embedded: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


class RetrievalIndex:
    """A persistent, incrementally updated index of the ecosystem documents."""

    def __init__(self, directory: Path | None = None, embedder: Embedder | None = None) -> None:
        if embedder is None:
            from ecosystem_assistant.knowledge.retrieval.embedders import embedder_by_name

            embedder = embedder_by_name()
        self.embedder = embedder
        self.directory = Path(directory) if directory is not None else self.default_directory()
        self.directory.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self.directory), settings=Settings(anonymized_telemetry=False)
        )
        self._collection = self._open_or_create()

    # --- location and opening ---------------------------------------------------------------

    @staticmethod
    def default_directory() -> Path:
        configured = os.environ.get("VECTOR_INDEX_DIR")
        return Path(configured) if configured else REPO_ROOT / "var" / "index"

    @classmethod
    def recreate(cls, directory: Path | None, embedder: Embedder | None = None) -> "RetrievalIndex":
        """Drop any existing index in ``directory`` and start an empty one with ``embedder``."""
        target = Path(directory) if directory is not None else cls.default_directory()
        target.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(target), settings=Settings(anonymized_telemetry=False))
        if COLLECTION in _names(client):
            client.delete_collection(COLLECTION)
        return cls(target, embedder)

    def _open_or_create(self):
        if COLLECTION in _names(self._client):
            collection = self._client.get_collection(COLLECTION, embedding_function=None)
            meta = collection.metadata or {}
            if meta.get("embedder") != self.embedder.name or meta.get("dim") != self.embedder.dim:
                raise IndexMismatchError(
                    f"The index in {self.directory} was built with embedder {meta.get('embedder')!r} "
                    f"(dim {meta.get('dim')}) but was opened with {self.embedder.name!r} (dim {self.embedder.dim}). "
                    f"Rebuild the index with RetrievalIndex.recreate(...) or delete that folder."
                )
            return collection
        return self._client.create_collection(
            COLLECTION,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={"embedder": self.embedder.name, "dim": self.embedder.dim},
            embedding_function=None,
        )

    @property
    def telemetry_enabled(self) -> bool:
        return bool(self._client.get_settings().anonymized_telemetry)

    # --- reading what is stored -------------------------------------------------------------------

    def chunk_count(self) -> int:
        return self._collection.count()

    def stored_versions(self) -> dict[str, str]:
        """``{document path: version}`` of everything in the index."""
        stored = self._collection.get(include=["metadatas"])
        return {m["path"]: m["version"] for m in stored["metadatas"]}

    def chunks_of(self, path: str) -> list[dict[str, Any]]:
        """The stored chunks of one document, in document order (``id``, ``text``, ``metadata``)."""
        stored = self._collection.get(where={"path": path}, include=["documents", "metadatas"])
        items = [
            {"id": i, "text": t, "metadata": dict(m)}
            for i, t, m in zip(stored["ids"], stored["documents"], stored["metadatas"])
        ]
        return sorted(items, key=lambda item: item["metadata"]["chunk_index"])

    # --- search ----------------------------------------------------------------------------------

    def search(
        self,
        question: str,
        k: int = DEFAULT_RESULTS,
        client: str | None = None,
        application: str | None = None,
        service: str | None = None,
        include_obsolete: bool = False,
    ) -> list[Hit]:
        """The best chunks for ``question``, at most ``k`` (never more than 20), each with its citation.

        Chunks of obsolete documents are left out unless ``include_obsolete`` is true.
        """
        return run_search(self._collection, self.embedder, question, k, client, application, service,
                          include_obsolete)

    # --- keeping the index in step with the files --------------------------------------------------

    def sync(self, root: Path, graph: KnowledgeGraph | None = None) -> SyncReport:
        """Embed only the documents that are new or whose version changed; drop the ones that vanished."""
        root = Path(root)
        context = ServiceContext.from_graph(graph if graph is not None else build_graph(root))
        stored = self.stored_versions()
        on_disk = discover_documents(root)

        added = updated = unchanged = empty = embedded = 0
        for path in on_disk:
            chunks = load_chunks(root, path, context)
            if not chunks:  # a title with no text of its own: there is nothing to retrieve
                empty += 1
                if path in stored:
                    self._collection.delete(where={"path": path})
                    updated += 1
                continue
            if path in stored and stored[path] == chunks[0].version:
                unchanged += 1
                continue
            if path in stored:
                self._collection.delete(where={"path": path})
                updated += 1
            else:
                added += 1
            vectors = self.embedder.embed([c.text for c in chunks])
            self._collection.add(
                ids=[c.id for c in chunks],
                embeddings=vectors,
                documents=[c.text for c in chunks],
                metadatas=[c.metadata() for c in chunks],
            )
            embedded += len(chunks)

        removed = 0
        for path in sorted(set(stored) - set(on_disk)):
            self._collection.delete(where={"path": path})
            removed += 1
        return SyncReport(added, updated, removed, unchanged, empty, embedded)


def _names(client: Any) -> list[str]:
    return [c if isinstance(c, str) else c.name for c in client.list_collections()]
