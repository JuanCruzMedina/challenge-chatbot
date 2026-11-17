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


# --- improve-search-and-edits: listing and team overview -------------------------------------------

def test_every_team_can_be_listed(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.list_entities("team")
    assert result.found is True
    names = [e.name for e in result.entities]
    assert {"orders-team", "driver-team", "tracking-team"} <= set(names)
    assert names == sorted(names)
    assert result.sources  # the files the teams come from


def test_a_loose_type_name_is_understood(sample_graph: KnowledgeGraph) -> None:
    assert [e.id for e in sample_graph.list_entities("Teams").entities] == [
        e.id for e in sample_graph.list_entities("team").entities
    ]


def test_an_unknown_type_names_the_valid_ones(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.list_entities("planet")
    assert result.found is False
    assert {"team", "person", "service"} <= {s.name for s in result.suggestions}


def test_a_team_with_its_services_and_leads(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.team_overview("orders-team")
    assert result.found is True
    assert result.team.id == "team:orders-team"
    owned = {s.service.id: s.lead.name if s.lead else None for s in result.services}
    assert owned["service:orders-service"] == "Tomás Aguirre"
    assert "repos/orders-service/service.yaml" in result.sources


def test_an_unknown_team_is_not_found(sample_graph: KnowledgeGraph) -> None:
    assert sample_graph.team_overview("ghost-team").found is False
