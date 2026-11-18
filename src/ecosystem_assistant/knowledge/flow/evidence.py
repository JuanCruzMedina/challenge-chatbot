"""Evidence for the answer: numbered graph facts and document passages (design.md D-5, D-6).

Facts are ``K1..`` (one per executed graph query) and passages are ``D1..`` (the search results that
reach the minimum score). The model is only ever given evidence from here, and it cites these ids.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from ecosystem_assistant.knowledge.flow.plan import Plan, PlannedQuery
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex

MAX_NEIGHBOURS = 4
FACT_MAX_CHARS = 3000
MAX_EVIDENCE_CHARS = 12000
TRUNCATED = " …[truncated]"


@dataclass(frozen=True)
class Fact:
    id: str                 # "K1"
    method: str
    arguments: dict[str, str]
    found: bool
    text: str               # compact JSON of the result, or a "not found" note with suggestions
    sources: list[str]
    truncated: bool = False  # the text was cut at the cap: the list may be incomplete


@dataclass(frozen=True)
class Passage:
    id: str                 # "D1"
    text: str               # starts with the heading path
    score: float
    path: str
    heading_path: str
    title: str
    client: str
    service: str
    status: str
    neighbour: bool = False  # not ranked: another section of the best document, added for context


@dataclass
class SearchResult:
    passages: list[Passage]
    below_threshold: int    # results the search returned but whose score was under the minimum
    searched: int           # results the search returned


@dataclass
class Evidence:
    text: str
    facts: list[Fact]
    passages: list[Passage]  # the passages that fit in the text
    dropped_passages: int = 0


# --- graph facts ---------------------------------------------------------------------------------

def _compact(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def run_graph_queries(graph: KnowledgeGraph, queries: list[PlannedQuery],
                      max_chars: int = FACT_MAX_CHARS) -> list[Fact]:
    """Run each validated query on the graph. A name that is not found is still a fact (with suggestions)."""
    facts: list[Fact] = []
    for number, query in enumerate(queries, start=1):
        result = getattr(graph, query.method)(**query.arguments)
        data = result.to_dict()
        if data["found"]:
            text = _compact({k: v for k, v in data.items() if k not in ("sources", "found")})
            sources = list(data["sources"])
        else:
            names = ", ".join(s["name"] for s in data["suggestions"]) or "none"
            text = f"Not found: {data['query']!r}. Close names: {names}."
            sources = []
        cut = len(text) > max_chars
        if cut:
            text = text[:max_chars] + TRUNCATED
        facts.append(Fact(f"K{number}", query.method, dict(query.arguments), bool(data["found"]), text, sources, cut))
    return facts


# --- document passages -----------------------------------------------------------------------------

def search_documents(index: RetrievalIndex, question: str, plan: Plan, min_score: float, k: int = 5) -> SearchResult:
    """Search the documents (always) with the plan's filters; keep the hits that reach ``min_score``."""
    hits = index.search(
        question, k=k,
        client=plan.filters.get("client"), application=plan.filters.get("application"),
        service=plan.filters.get("service"), include_obsolete=plan.include_obsolete,
    )
    kept = [h for h in hits if h.score >= min_score]
    passages = [
        Passage(f"D{number}", h.text, h.score, h.citation.path, h.citation.heading_path, h.citation.title,
                h.citation.client, h.citation.service, h.citation.status)
        for number, h in enumerate(kept, start=1)
    ]
    if kept:
        passages += _neighbour_sections(index, kept, start=len(passages) + 1)
    return SearchResult(passages, below_threshold=len(hits) - len(kept), searched=len(hits))


def _neighbour_sections(index: RetrievalIndex, kept: list[Any], start: int) -> list[Passage]:
    """The other sections of the best-ranked document, in document order, as context for its ranked sections.

    A runbook is several sections and the question often matches only one of them (the symptom), while the answer is
    in another (the steps). Only the best document is completed, at most ``MAX_NEIGHBOURS`` sections, and a section
    that was ranked already is not repeated.
    """
    best = kept[0]
    ranked = {(h.citation.path, h.citation.heading_path) for h in kept}
    extra = [c for c in index.chunks_of(best.citation.path)
             if (c["metadata"]["path"], c["metadata"]["heading_path"]) not in ranked][:MAX_NEIGHBOURS]
    return [
        Passage(f"D{number}", chunk["text"], best.score, meta["path"], meta["heading_path"], meta["title"],
                meta["client"], meta["service"], meta["status"], neighbour=True)
        for number, chunk in enumerate(extra, start=start) for meta in [chunk["metadata"]]
    ]


# --- putting it together for the model ----------------------------------------------------------

def has_evidence(facts: list[Fact], passages: list[Passage]) -> bool:
    """Evidence exists when at least one graph query found something or one passage reached the minimum score."""
    return any(f.found for f in facts) or bool(passages)


def build_evidence(facts: list[Fact], passages: list[Passage], max_chars: int = MAX_EVIDENCE_CHARS) -> Evidence:
    """The numbered text given to the model. Facts always go in; passages go in best first while they fit."""
    parts: list[str] = []
    if facts:
        parts.append("GRAPH FACTS (from the knowledge graph)")
        for fact in facts:
            arguments = ", ".join(f"{k}={v}" for k, v in fact.arguments.items())
            parts.append(f"[{fact.id}] {fact.method}({arguments}): {fact.text}")
    kept: list[Passage] = []
    if passages:
        header = "DOCUMENT PASSAGES (from the documentation)"
        used = len("\n\n".join(parts)) + (len(header) + 2 if parts else len(header))
        blocks: list[str] = []
        for passage in passages:
            block = f"[{passage.id}] {passage.path} (score {passage.score:.2f})\n{passage.text}"
            if used + len(block) + 2 > max_chars:
                break
            blocks.append(block)
            kept.append(passage)
            used += len(block) + 2
        if blocks:
            parts.append(header)
            parts.extend(blocks)
    return Evidence("\n\n".join(parts), facts, kept, dropped_passages=len(passages) - len(kept))
