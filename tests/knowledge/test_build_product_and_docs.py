"""Spec: product data becomes entities and relations; documents carry their title and status."""
from __future__ import annotations

from pathlib import Path

from ecosystem_assistant.actions.tools.documents import set_obsolete
from ecosystem_assistant.actions.workspace import Workspace
from ecosystem_assistant.knowledge.graph.build import build_graph
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from tests.knowledge.helpers import ids, incoming, node, out


def test_every_feature_is_part_of_an_epic_and_every_epic_belongs_to_a_client(sample_graph: KnowledgeGraph) -> None:
    features = ids(sample_graph, "feature")
    assert len(features) == 7 and len(ids(sample_graph, "epic")) == 5
    for feature in features:
        assert len(out(sample_graph, feature, "PART_OF")) == 1, feature
    for epic in ids(sample_graph, "epic"):
        assert len(out(sample_graph, epic, "BELONGS_TO")) == 1, epic
    assert out(sample_graph, "epic:LOG-EPIC-02", "BELONGS_TO") == ["client:demo-logistics"]
    assert out(sample_graph, "epic:EPIC-01", "BELONGS_TO") == ["client:demo-grocery"]


def test_features_are_linked_to_the_services_that_implement_them(sample_graph: KnowledgeGraph) -> None:
    assert incoming(sample_graph, "feature:LOG-FEAT-102", "IMPLEMENTS") == [
        "service:driver-service", "service:routing-service",
    ]
    assert node(sample_graph, "feature:FEAT-102")["attributes"]["status"] == "in_progress"


def test_every_client_has_its_own_vision_document(sample_graph: KnowledgeGraph) -> None:
    assert out(sample_graph, "client:demo-logistics", "HAS_VISION") == [
        "doc:clients/demo-logistics/product/vision.md"
    ]
    assert out(sample_graph, "client:demo-grocery", "HAS_VISION") == [
        "doc:clients/demo-grocery/product/vision.md"
    ]
    assert node(sample_graph, "doc:clients/demo-logistics/product/vision.md")["attributes"]["title"] == (
        "Product vision: Demo Logistics"
    )


def test_documents_have_a_title_and_a_current_status(sample_graph: KnowledgeGraph) -> None:
    doc = node(sample_graph, "doc:orders-service/docs/api.md")
    assert doc["attributes"]["title"] == "orders-api v1"
    assert doc["attributes"]["status"] == "current"
    assert out(sample_graph, "service:orders-service", "DOCUMENTED_BY") == [
        "doc:orders-service/README.md",
        "doc:orders-service/docs/adr-001-event-driven-orders.md",
        "doc:orders-service/docs/api.md",
        "doc:orders-service/docs/runbook-stuck-order.md",
    ]


def test_a_document_marked_obsolete_by_the_actions_server_shows_as_obsolete(sample_copy: Path, tmp_path: Path) -> None:
    workspace = Workspace(root=sample_copy, audit_file=tmp_path / "audit.jsonl")
    set_obsolete(workspace, "payments-service", "docs/api-v1.md", "Replaced by v2", "docs/api-v2.md")

    graph = build_graph(sample_copy)

    obsolete = node(graph, "doc:payments-service/docs/api-v1.md")["attributes"]
    assert obsolete["status"] == "obsolete"
    assert obsolete["obsolete_reason"] == "Replaced by v2"
    assert obsolete["replaced_by"] == "docs/api-v2.md"
    assert obsolete["title"] == "payments-api v1"  # the heading is still found after the front matter
    others = [n for n in graph.nodes("document") if n["id"] != "doc:payments-service/docs/api-v1.md"]
    assert others and all(n["attributes"]["status"] == "current" for n in others)
