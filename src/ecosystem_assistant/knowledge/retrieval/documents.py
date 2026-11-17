"""Which documents are indexed, and the metadata of their chunks (design.md D-4, D-5, D-6).

The scope comes from the path; application and client of a service come from the knowledge graph.
A folder the graph does not know is still indexed, with empty application and client.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ecosystem_assistant.knowledge.graph import model as graph_model
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from ecosystem_assistant.knowledge.retrieval.chunking import Chunk, chunk_document

# Where documents live inside a data root. Nothing else (in particular nothing under prs/) is indexed.
PATTERNS = ("repos/*/**/*.md", "clients/*/product/**/*.md", "company/**/*.md")


def discover_documents(root: Path) -> list[str]:
    """Root-relative POSIX paths of the documents to index, sorted. Hidden files are skipped."""
    root = Path(root)
    found: set[str] = set()
    for pattern in PATTERNS:
        for path in root.glob(pattern):
            relative = path.relative_to(root)
            if path.is_file() and not any(part.startswith(".") for part in relative.parts):
                found.add(relative.as_posix())
    return sorted(found)


class ServiceContext:
    """Application and client of every service the graph knows."""

    def __init__(self, contexts: dict[str, tuple[str, str]]) -> None:
        self._contexts = contexts

    @classmethod
    def from_graph(cls, graph: KnowledgeGraph) -> "ServiceContext":
        contexts: dict[str, tuple[str, str]] = {}
        for node in graph.nodes(graph_model.SERVICE):
            # The exact node key is used on purpose: a name is never resolved by similarity here.
            result = graph.service_product_context(node["id"])
            if not result.found:
                continue
            application = graph_model.split_key(result.application.id)[1] if result.application else ""
            client = graph_model.split_key(result.client.id)[1] if result.client else ""
            contexts[node["name"]] = (application, client)
        return cls(contexts)

    def of(self, service: str) -> tuple[str, str]:
        return self._contexts.get(service, ("", ""))


@dataclass(frozen=True)
class IndexedChunk:
    chunk: Chunk
    scope: str        # "service", "client" or "company"
    service: str
    application: str
    client: str
    version: str      # changes when the file or its graph context changes

    @property
    def id(self) -> str:
        return self.chunk.id

    @property
    def text(self) -> str:
        return self.chunk.text

    def metadata(self) -> dict[str, str | int]:
        """Flat metadata as stored next to the vector (the vector store accepts only scalar values)."""
        return {
            "path": self.chunk.path,
            "title": self.chunk.title,
            "heading_path": self.chunk.heading_path,
            "scope": self.scope,
            "service": self.service,
            "application": self.application,
            "client": self.client,
            "status": self.chunk.status,
            "content_hash": self.chunk.content_hash,
            "version": self.version,
            "chunk_index": self.chunk.index,
        }


def _scope_of(relative_path: str) -> tuple[str, str, str]:
    """``(scope, service, client)`` taken from the path alone."""
    parts = relative_path.split("/")
    if parts[0] == "repos":
        return "service", parts[1], ""
    if parts[0] == "clients":
        return "client", "", parts[1]
    return "company", "", ""


def load_chunks(root: Path, relative_path: str, context: ServiceContext) -> list[IndexedChunk]:
    """Read one document and return its chunks with their metadata."""
    text = (Path(root) / relative_path).read_bytes().decode("utf-8")
    scope, service, client = _scope_of(relative_path)
    application = ""
    if scope == "service":
        application, client = context.of(service)
    chunks = chunk_document(relative_path, text)
    if not chunks:
        return []
    version = hashlib.sha256(
        f"{chunks[0].content_hash}|{service}|{application}|{client}".encode("utf-8")
    ).hexdigest()
    return [IndexedChunk(c, scope, service, application, client, version) for c in chunks]
