"""Spec: structural questions - client overview, application services, owner, describe."""
from __future__ import annotations

from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph


def test_a_clients_applications_and_services(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.client_overview("demo-logistics")
    assert result.found is True
    assert result.client.id == "client:demo-logistics"
    layout = {a.application.id: [s.id for s in a.services] for a in result.applications}
    assert layout == {
        "application:driver-app": ["service:driver-service"],
        "application:fleet-tracker": ["service:routing-service", "service:tracking-service"],
    }
    assert result.vision.id == "doc:clients/demo-logistics/product/vision.md"


def test_loose_client_names_work(sample_graph: KnowledgeGraph) -> None:
    assert sample_graph.client_overview("Demo Grocery").client.id == "client:demo-grocery"


def test_the_services_of_an_application(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.application_services("storefront")
    assert result.client.id == "client:demo-grocery"
    assert [s.id for s in result.services] == [
        "service:catalog-service", "service:notifications-service",
        "service:orders-service", "service:payments-service",
    ]


def test_owner_and_lead_of_a_service(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.service_owner("tracking-service")
    assert result.service.id == "service:tracking-service"
    assert result.team.id == "team:tracking-team"
    assert result.lead.name == "Bruno Salas"
    assert result.sources == ["repos/tracking-service/service.yaml"]


def test_describing_an_entity_groups_its_relations(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.describe("payments-service")
    assert result.entity.id == "service:payments-service"
    assert result.attributes["lifecycle"] == "production"

    groups = {(g.relation, g.direction): [e.id for e in g.entities] for g in result.relations}
    assert groups[("OWNED_BY", "out")] == ["team:payments-team"]
    assert groups[("PROVIDES", "out")] == ["api:payments-api"]
    assert groups[("PUBLISHES", "out")] == ["event:payment.confirmed", "event:payment.failed"]
    assert groups[("HAS_SERVICE", "in")] == ["application:storefront"]
    assert ("CONSUMES", "in") not in groups  # nothing points at a service with CONSUMES; consumers point at the API
    assert "repos/payments-service/service.yaml" in result.sources
