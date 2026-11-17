"""Spec: product context of a service, relation paths and obsolete documents."""
from __future__ import annotations

from pathlib import Path

from ecosystem_assistant.actions.tools.documents import set_obsolete
from ecosystem_assistant.actions.workspace import Workspace
from ecosystem_assistant.knowledge.graph.build import build_graph
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph


def test_the_product_context_of_a_service_uses_its_own_clients_vision(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.service_product_context("driver-service")

    assert result.service.id == "service:driver-service"
    assert result.application.id == "application:driver-app"
    assert result.client.id == "client:demo-logistics"
    assert {f.feature.id: (f.epic.id, f.status) for f in result.features} == {
        "feature:LOG-FEAT-101": ("epic:LOG-EPIC-01", "released"),
        "feature:LOG-FEAT-102": ("epic:LOG-EPIC-02", "in_progress"),
        "feature:LOG-FEAT-201": ("epic:LOG-EPIC-02", "planned"),
    }
    assert result.vision.document.id == "doc:clients/demo-logistics/product/vision.md"
    assert result.vision.title == "Product vision: Demo Logistics"
    assert "demo-grocery" not in result.vision.path


def test_the_grocery_services_get_the_grocery_vision(sample_graph: KnowledgeGraph) -> None:
    assert sample_graph.service_product_context("orders-service").vision.document.id == (
        "doc:clients/demo-grocery/product/vision.md"
    )


def test_a_path_goes_through_a_shared_api(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.relation_path("tracking-service", "driver-service")

    assert result.connected is True
    assert result.start.id == "service:tracking-service" and result.end.id == "service:driver-service"
    assert [(s.source.id, s.relation, s.direction, s.target.id) for s in result.steps] == [
        ("service:tracking-service", "PROVIDES", "out", "api:tracking-api"),
        ("api:tracking-api", "CONSUMES", "in", "service:driver-service"),
    ]


def test_a_path_between_unconnected_entities_is_empty(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.relation_path("catalog-service", "tracking-service")
    assert result.connected is False
    assert result.steps == []


def test_belonging_to_the_same_company_is_not_a_connection(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.relation_path("Demo Grocery", "Demo Logistics")
    assert result.connected is False and result.steps == []


def test_a_path_never_uses_the_company_relation(sample_graph: KnowledgeGraph) -> None:
    for a, b in (("orders-service", "driver-service"), ("catalog-service", "routing-service")):
        assert all(s.relation != "HAS_CLIENT" for s in sample_graph.relation_path(a, b).steps)


def test_a_path_from_an_entity_to_itself_is_connected_and_empty(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.relation_path("orders-service", "orders-service")
    assert result.connected is True and result.steps == []


def test_no_document_is_obsolete_in_the_committed_data(sample_graph: KnowledgeGraph) -> None:
    assert sample_graph.obsolete_documents().documents == []


def test_obsolete_documents_are_listed_with_service_and_path(sample_copy: Path, tmp_path: Path) -> None:
    workspace = Workspace(root=sample_copy, audit_file=tmp_path / "audit.jsonl")
    set_obsolete(workspace, "payments-service", "docs/api-v1.md", "Replaced by v2", "docs/api-v2.md")

    result = build_graph(sample_copy).obsolete_documents()

    assert [(d.document.id, d.service, d.path, d.reason, d.replaced_by) for d in result.documents] == [
        ("doc:payments-service/docs/api-v1.md", "payments-service", "docs/api-v1.md",
         "Replaced by v2", "docs/api-v2.md")
    ]
    assert "repos/payments-service/docs/api-v1.md" in result.sources
