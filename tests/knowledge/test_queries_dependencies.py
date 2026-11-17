"""Spec: structural questions - API consumers (incl. deprecation) and event flow."""
from __future__ import annotations

from pathlib import Path

from ecosystem_assistant.knowledge.graph.build import build_graph
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from tests.data.fixture import edit


def test_consumers_of_an_api_come_with_application_and_client(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.api_consumers("payments-api")
    assert result.api.id == "api:payments-api"
    assert [p.service.id for p in result.providers] == ["service:payments-service"]
    assert [(c.service.id, c.application.id, c.client.id) for c in result.consumers] == [
        ("service:orders-service", "application:storefront", "client:demo-grocery")
    ]
    assert result.deprecated == []


def test_an_api_with_no_consumer_has_an_empty_list(sample_graph: KnowledgeGraph) -> None:
    assert sample_graph.api_consumers("orders-api").consumers == []


def test_a_deprecated_version_is_reported_with_its_consumers(sample_copy: Path) -> None:
    edit(
        sample_copy / "repos" / "payments-service" / "service.yaml",
        lambda m: m["provides_apis"][0].update(status="deprecated", sunset="2027-03-31"),
    )
    result = build_graph(sample_copy).api_consumers("payments-api")

    assert [(d.provider.id, d.version, d.sunset) for d in result.deprecated] == [
        ("service:payments-service", "v1", "2027-03-31")
    ]
    assert [c.service.id for c in result.consumers] == ["service:orders-service"]


def test_the_flow_of_an_event(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.event_flow("route.assigned")
    assert result.event.id == "event:route.assigned"
    assert [s.id for s in result.publishers] == ["service:routing-service"]
    assert [s.id for s in result.subscribers] == ["service:driver-service"]


def test_an_event_with_several_subscribers(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.event_flow("payment failed")
    assert [s.id for s in result.publishers] == ["service:payments-service"]
    assert [s.id for s in result.subscribers] == ["service:notifications-service", "service:orders-service"]
