"""Spec: entities can be found by name (loose wording, ranked, no error when nothing matches)."""
from __future__ import annotations

from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph


def test_an_exact_name_resolves_to_one_entity(sample_graph: KnowledgeGraph) -> None:
    candidates = sample_graph.find_entities("orders-service")
    assert candidates[0].id == "service:orders-service"
    assert candidates[0].type == "service"
    assert [c.id for c in candidates if c.match == "exact"] == ["service:orders-service"]


def test_loose_wording_resolves_to_the_right_entity(sample_graph: KnowledgeGraph) -> None:
    for text in ("Payments API", "payments_api", "PAYMENTS-API", "payments   api"):
        assert sample_graph.find_entities(text)[0].id == "api:payments-api", text


def test_an_ambiguous_name_returns_several_candidates_with_their_types(sample_graph: KnowledgeGraph) -> None:
    candidates = sample_graph.find_entities("payments")
    by_id = {c.id: c.type for c in candidates}
    assert by_id["service:payments-service"] == "service"
    assert by_id["api:payments-api"] == "api"
    assert by_id["team:payments-team"] == "team"
    assert [c.id for c in candidates[:3]] == ["service:payments-service", "api:payments-api", "team:payments-team"]


def test_an_unknown_name_returns_an_empty_list(sample_graph: KnowledgeGraph) -> None:
    assert sample_graph.find_entities("zzzz nothing like this") == []
    assert sample_graph.find_entities("") == []
    assert sample_graph.find_entities("   ") == []


def test_results_can_be_filtered_by_type_and_limited(sample_graph: KnowledgeGraph) -> None:
    only_apis = sample_graph.find_entities("payments", type="api")
    assert [c.id for c in only_apis] == ["api:payments-api"]
    assert len(sample_graph.find_entities("service", limit=3)) == 3


def test_ranking_is_deterministic(sample_graph: KnowledgeGraph) -> None:
    assert sample_graph.find_entities("service") == sample_graph.find_entities("service")
