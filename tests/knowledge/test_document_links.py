"""Spec: documents say what they are about; the documents about an entity can be listed (add-document-links-graph)."""
from __future__ import annotations

from pathlib import Path

from ecosystem_assistant.knowledge.graph.build import build_graph
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph


def _write(root: Path, service: str, doc_path: str, front: str, body: str = "# Note\n\nSomething.\n") -> str:
    path = root / "repos" / service / doc_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{front}\n---\n{body}" if front else body, encoding="utf-8")
    return f"doc:{service}/{doc_path}"


def _relations(graph: KnowledgeGraph, key: str) -> dict[tuple[str, str], list[str]]:
    description = graph.describe(key)
    return {(g.relation, g.direction): [e.id for e in g.entities] for g in description.relations}


def test_a_document_no_manifest_lists_is_read(sample_copy: Path) -> None:
    key = _write(sample_copy, "orders-service", "docs/payments-note.md", "about: [payments-service, payments-api]")

    graph = build_graph(sample_copy)

    relations = _relations(graph, key)
    assert relations[("DOCUMENTED_BY", "in")] == ["service:orders-service"]
    assert relations[("ABOUT", "out")] == ["api:payments-api", "service:payments-service"]


def test_a_single_name_is_accepted(sample_copy: Path) -> None:
    key = _write(sample_copy, "orders-service", "docs/one.md", "about: payments-api")
    assert _relations(build_graph(sample_copy), key)[("ABOUT", "out")] == ["api:payments-api"]


def test_an_unknown_name_is_reported_and_the_build_succeeds(sample_copy: Path) -> None:
    key = _write(sample_copy, "orders-service", "docs/ghost.md", "about: [payments-api, ghost-service]")

    graph = build_graph(sample_copy)

    assert _relations(graph, key)[("ABOUT", "out")] == ["api:payments-api"]
    assert graph.unresolved_links == [{"document": "orders-service/docs/ghost.md", "name": "ghost-service"}]


def test_a_document_with_no_about_is_not_added_and_data_without_links_has_none_unresolved(sample_copy: Path) -> None:
    _write(sample_copy, "orders-service", "docs/plain.md", "")
    graph = build_graph(sample_copy)

    assert "doc:orders-service/docs/plain.md" not in {n["id"] for n in graph.nodes("document")}
    assert graph.unresolved_links == []


def test_a_manifest_document_with_links_is_one_entity(sample_copy: Path) -> None:
    path = sample_copy / "repos" / "orders-service" / "docs" / "api.md"
    path.write_text("---\nabout: [payments-api]\n---\n" + path.read_text(encoding="utf-8"), encoding="utf-8")

    graph = build_graph(sample_copy)

    ids = [n["id"] for n in graph.nodes("document") if n["id"] == "doc:orders-service/docs/api.md"]
    assert ids == ["doc:orders-service/docs/api.md"]
    relations = _relations(graph, "doc:orders-service/docs/api.md")
    assert relations[("ABOUT", "out")] == ["api:payments-api"] and ("DOCUMENTED_BY", "in") in relations


def test_documents_about_an_api(sample_copy: Path) -> None:
    _write(sample_copy, "orders-service", "docs/a.md", "about: [payments-api]", "# Alpha\n")
    _write(sample_copy, "driver-service", "docs/b.md", "about: payments-api", "# Beta\n")

    result = build_graph(sample_copy).documents_about("payments-api")

    assert result.found is True and result.entity.id == "api:payments-api"
    listed = {(d.service, d.path, d.title, d.via, d.status) for d in result.documents}
    assert ("orders-service", "docs/a.md", "Alpha", "about", "current") in listed
    assert ("driver-service", "docs/b.md", "Beta", "about", "current") in listed


def test_a_service_lists_its_manifest_documents_and_the_ones_about_it(sample_copy: Path) -> None:
    _write(sample_copy, "orders-service", "docs/about-payments.md", "about: payments-service", "# About payments\n")

    result = build_graph(sample_copy).documents_about("payments-service")

    via = {(d.path, d.via) for d in result.documents if d.service == "payments-service"}
    assert ("docs/api-v1.md", "documented_by") in via
    assert ("docs/about-payments.md", "about") in {(d.path, d.via) for d in result.documents}
    assert result.sources, "the answer says where it comes from"


def test_an_unknown_entity_is_not_found_with_suggestions(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.documents_about("paymnts-api")
    assert result.found is False and "api:payments-api" in [s.id for s in result.suggestions]
