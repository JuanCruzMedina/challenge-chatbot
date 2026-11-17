"""Helpers for the knowledge graph tests: read relations from the graph's plain-data export."""
from __future__ import annotations

from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph


def out(kg: KnowledgeGraph, source: str, relation: str) -> list[str]:
    """Sorted targets of the edges ``source --relation--> target``."""
    return sorted(e["target"] for e in kg.edges(relation) if e["source"] == source)


def incoming(kg: KnowledgeGraph, target: str, relation: str) -> list[str]:
    """Sorted sources of the edges ``source --relation--> target``."""
    return sorted(e["source"] for e in kg.edges(relation) if e["target"] == target)


def ids(kg: KnowledgeGraph, type_: str) -> list[str]:
    return sorted(n["id"] for n in kg.nodes(type_))


def node(kg: KnowledgeGraph, node_id: str) -> dict:
    found = [n for n in kg.nodes() if n["id"] == node_id]
    assert len(found) == 1, f"expected exactly one node {node_id!r}, found {len(found)}"
    return found[0]


def edge(kg: KnowledgeGraph, source: str, relation: str, target: str) -> dict:
    found = [e for e in kg.edges(relation) if e["source"] == source and e["target"] == target]
    assert len(found) == 1, f"expected exactly one edge {source} -{relation}-> {target}"
    return found[0]
