"""Spec: query results are plain data with provenance; unknown entities give a not-found result."""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from tests.data.helpers import SAMPLE

ANSWERED: dict[str, Callable[[KnowledgeGraph], Any]] = {
    "client_overview": lambda kg: kg.client_overview("demo-grocery"),
    "application_services": lambda kg: kg.application_services("fleet-tracker"),
    "service_owner": lambda kg: kg.service_owner("orders-service"),
    "api_consumers": lambda kg: kg.api_consumers("tracking-api"),
    "event_flow": lambda kg: kg.event_flow("order.created"),
    "service_product_context": lambda kg: kg.service_product_context("catalog-service"),
    "relation_path": lambda kg: kg.relation_path("tracking-service", "driver-service"),
    "describe": lambda kg: kg.describe("orders-service"),
}

MISSPELLED: dict[str, tuple[Callable[[KnowledgeGraph], Any], str]] = {
    "client_overview": (lambda kg: kg.client_overview("demo-grocey"), "client:demo-grocery"),
    "application_services": (lambda kg: kg.application_services("storefrnt"), "application:storefront"),
    "service_owner": (lambda kg: kg.service_owner("ordres-service"), "service:orders-service"),
    "api_consumers": (lambda kg: kg.api_consumers("paymnts-api"), "api:payments-api"),
    "event_flow": (lambda kg: kg.event_flow("order.creatd"), "event:order.created"),
    "service_product_context": (lambda kg: kg.service_product_context("ordres-service"), "service:orders-service"),
    "describe": (lambda kg: kg.describe("ordres-service"), "service:orders-service"),
    "relation_path (first)": (lambda kg: kg.relation_path("ordres-service", "driver-service"), "service:orders-service"),
    "relation_path (second)": (lambda kg: kg.relation_path("orders-service", "drivr-service"), "service:driver-service"),
}


@pytest.mark.parametrize("name", sorted(ANSWERED))
def test_results_serialize_to_json_and_cite_existing_sources(sample_graph: KnowledgeGraph, name: str) -> None:
    result = ANSWERED[name](sample_graph)
    data = result.to_dict()

    assert json.loads(json.dumps(data)) == data
    assert data["found"] is True
    assert data["sources"], name
    for source in data["sources"]:
        assert (SAMPLE / source).is_file(), f"{name}: {source}"


def test_find_entities_candidates_are_plain_data_too(sample_graph: KnowledgeGraph) -> None:
    data = [c.to_dict() for c in sample_graph.find_entities("payments")]
    assert json.loads(json.dumps(data)) == data
    assert set(data[0]) == {"id", "type", "name", "match"}


@pytest.mark.parametrize("name", sorted(MISSPELLED))
def test_a_misspelled_entity_gives_a_not_found_result_with_suggestions(
    sample_graph: KnowledgeGraph, name: str
) -> None:
    query, expected = MISSPELLED[name]
    result = query(sample_graph)  # must not raise

    data = result.to_dict()
    assert json.loads(json.dumps(data)) == data
    assert result.found is False and data["found"] is False
    assert data["suggestions"][0]["id"] == expected, "the closest name must come first"
    assert data["message"]


def test_a_name_with_no_close_match_has_no_suggestions(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.service_owner("qqqqqqqqqq")
    assert result.found is False and result.suggestions == []


def test_an_entity_of_the_wrong_type_is_not_found(sample_graph: KnowledgeGraph) -> None:
    result = sample_graph.service_owner("payments-api")  # an API, not a service
    assert result.found is False
    assert "service:payments-service" in [s.id for s in result.suggestions]
