"""Search over the index: bounded, filtered, cited and deterministic (design.md D-7)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ecosystem_assistant.knowledge.retrieval.embedders import Embedder

DEFAULT_RESULTS = 5
MAX_RESULTS = 20


@dataclass(frozen=True)
class Citation:
    title: str
    heading_path: str
    path: str
    scope: str
    service: str
    application: str
    client: str
    status: str


@dataclass(frozen=True)
class Hit:
    text: str
    score: float  # similarity in [0, 1], higher is better
    citation: Citation

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_filter(client: str | None, application: str | None, service: str | None,
                 include_obsolete: bool) -> dict[str, Any] | None:
    conditions: list[dict[str, Any]] = []
    if client:
        conditions.append({"client": client})
    if application:
        conditions.append({"application": application})
    if service:
        conditions.append({"service": service})
    if not include_obsolete:
        conditions.append({"status": "current"})
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}


def run_search(
    collection: Any,
    embedder: Embedder,
    question: str,
    k: int = DEFAULT_RESULTS,
    client: str | None = None,
    application: str | None = None,
    service: str | None = None,
    include_obsolete: bool = False,
) -> list[Hit]:
    limit = max(0, min(int(k), MAX_RESULTS))
    total = collection.count()
    if limit == 0 or not question or not question.strip() or total == 0:
        return []

    vector = embedder.embed([question])[0]
    result = collection.query(
        query_embeddings=[vector],
        n_results=min(limit, total),
        where=build_filter(client, application, service, include_obsolete),
        include=["documents", "metadatas", "distances"],
    )
    hits = [
        Hit(
            text=document,
            score=max(0.0, min(1.0, 1.0 - float(distance))),
            citation=Citation(
                title=meta["title"], heading_path=meta["heading_path"], path=meta["path"], scope=meta["scope"],
                service=meta["service"], application=meta["application"], client=meta["client"],
                status=meta["status"],
            ),
        )
        for document, meta, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0])
    ]
    # Best first; equal scores are ordered by file and text so the same question always gives the same answer.
    return sorted(hits, key=lambda h: (-h.score, h.citation.path, h.text))
