"""Spec: The graph is built from the ecosystem data - service manifests become entities and relations."""
from __future__ import annotations

from pathlib import Path

from ecosystem_assistant.knowledge.graph.build import build_graph
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from tests.data.fixture import edit
from tests.knowledge.helpers import edge, ids, node, out


def test_orders_service_relations(sample_graph: KnowledgeGraph) -> None:
    s = "service:orders-service"
    assert out(sample_graph, s, "OWNED_BY") == ["team:orders-team"]
    assert out(sample_graph, s, "LED_BY") == ["person:Tomás Aguirre"]
    assert out(sample_graph, s, "PROVIDES") == ["api:orders-api"]
    assert out(sample_graph, s, "CONSUMES") == ["api:catalog-api", "api:payments-api"]
    assert out(sample_graph, s, "PUBLISHES") == ["event:order.cancelled", "event:order.created"]
    assert "event:payment.confirmed" in out(sample_graph, s, "SUBSCRIBES_TO")


def test_every_service_has_one_team_and_one_lead(sample_graph: KnowledgeGraph) -> None:
    for service in ids(sample_graph, "service"):
        assert len(out(sample_graph, service, "OWNED_BY")) == 1, service
        assert len(out(sample_graph, service, "LED_BY")) == 1, service


def test_entities_of_every_kind_exist(sample_graph: KnowledgeGraph) -> None:
    assert ids(sample_graph, "api") == ["api:catalog-api", "api:orders-api", "api:payments-api", "api:tracking-api"]
    assert len(ids(sample_graph, "event")) == 7
    assert len(ids(sample_graph, "team")) == 7
    assert len(ids(sample_graph, "person")) == 7
    assert node(sample_graph, "service:orders-service")["name"] == "orders-service"


def test_the_provides_edge_carries_the_api_versions(fx_graph: KnowledgeGraph) -> None:
    provides = edge(fx_graph, "service:svc-a1", "PROVIDES", "api:a1-api")
    assert provides["attributes"]["versions"] == [{"version": "v1", "status": "active"}]


def test_a_deprecated_version_keeps_its_status_and_sunset(fx_root: Path) -> None:
    edit(
        fx_root / "repos" / "svc-a1" / "service.yaml",
        lambda m: m.update(provides_apis=[
            {"id": "a1-api", "version": "v1", "status": "deprecated", "sunset": "2027-03-31", "doc": "docs/api.md"},
            {"id": "a1-api", "version": "v2", "status": "active"},
        ]),
    )
    provides = edge(build_graph(fx_root), "service:svc-a1", "PROVIDES", "api:a1-api")
    assert provides["attributes"]["versions"] == [
        {"version": "v1", "status": "deprecated", "sunset": "2027-03-31"},
        {"version": "v2", "status": "active"},
    ]
