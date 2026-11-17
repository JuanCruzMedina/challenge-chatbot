"""Spec: The graph is built from the ecosystem data - the hierarchy is represented."""
from __future__ import annotations

from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from tests.knowledge.helpers import ids, incoming, out


def test_the_committed_hierarchy_is_represented(sample_graph: KnowledgeGraph) -> None:
    assert ids(sample_graph, "company") == ["company:demo-studio"]
    assert out(sample_graph, "company:demo-studio", "HAS_CLIENT") == ["client:demo-grocery", "client:demo-logistics"]
    assert len(ids(sample_graph, "client")) == 2
    assert len(ids(sample_graph, "application")) == 3
    assert len(ids(sample_graph, "service")) == 7
    assert out(sample_graph, "client:demo-logistics", "HAS_APPLICATION") == [
        "application:driver-app", "application:fleet-tracker",
    ]
    assert out(sample_graph, "client:demo-grocery", "HAS_APPLICATION") == ["application:storefront"]
    assert out(sample_graph, "application:fleet-tracker", "HAS_SERVICE") == [
        "service:routing-service", "service:tracking-service",
    ]


def test_every_service_is_linked_to_exactly_one_application(sample_graph: KnowledgeGraph) -> None:
    for service in ids(sample_graph, "service"):
        assert len(incoming(sample_graph, service, "HAS_SERVICE")) == 1, service


def test_the_synthetic_hierarchy_is_represented_too(fx_graph: KnowledgeGraph) -> None:
    assert len(ids(fx_graph, "client")) == 2
    assert len(ids(fx_graph, "application")) == 3
    assert ids(fx_graph, "service") == ["service:svc-a1", "service:svc-a2", "service:svc-b1"]
    assert out(fx_graph, "application:app-a1", "HAS_SERVICE") == ["service:svc-a1"]
