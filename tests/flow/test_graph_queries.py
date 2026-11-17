"""Spec: planned graph queries run against the graph and become numbered facts with their sources."""
from __future__ import annotations

import json

from ecosystem_assistant.knowledge.flow.evidence import run_graph_queries
from ecosystem_assistant.knowledge.flow.plan import PlannedQuery
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph


def test_the_queries_run_and_become_numbered_facts_with_sources(sample_graph: KnowledgeGraph) -> None:
    facts = run_graph_queries(sample_graph, [
        PlannedQuery("api_consumers", {"api": "payments api"}),
        PlannedQuery("service_owner", {"service": "tracking-service"}),
    ])

    assert [f.id for f in facts] == ["K1", "K2"]
    first, second = facts
    assert (first.method, first.found) == ("api_consumers", True)
    assert "orders-service" in first.text
    assert "repos/orders-service/service.yaml" in first.sources
    assert "tracking-team" in second.text and "Bruno Salas" in second.text
    assert second.sources == ["repos/tracking-service/service.yaml"]


def test_the_fact_text_is_compact_json_without_the_sources_list(sample_graph: KnowledgeGraph) -> None:
    fact = run_graph_queries(sample_graph, [PlannedQuery("event_flow", {"event": "route.assigned"})])[0]

    data = json.loads(fact.text)
    assert "sources" not in data and "found" not in data
    assert [s["name"] for s in data["subscribers"]] == ["driver-service"]
    assert "\n" not in fact.text and ": " not in fact.text  # compact separators


def test_an_entity_that_is_not_found_becomes_a_fact_that_says_so_with_suggestions(sample_graph: KnowledgeGraph) -> None:
    fact = run_graph_queries(sample_graph, [PlannedQuery("service_owner", {"service": "ordres-service"})])[0]

    assert fact.id == "K1" and fact.found is False
    assert "not found" in fact.text.lower() and "orders-service" in fact.text
    assert fact.sources == []


def test_a_long_result_is_truncated_with_a_marker(sample_graph: KnowledgeGraph) -> None:
    fact = run_graph_queries(sample_graph, [PlannedQuery("describe", {"entity": "orders-service"})], max_chars=120)[0]

    assert fact.text.endswith("[truncated]")
    assert len(fact.text) <= 120 + len(" …[truncated]")
    assert fact.sources  # the sources are kept even when the text is cut


def test_no_queries_give_no_facts(sample_graph: KnowledgeGraph) -> None:
    assert run_graph_queries(sample_graph, []) == []


def test_every_method_of_the_catalog_runs_without_error(sample_graph: KnowledgeGraph) -> None:
    queries = [
        PlannedQuery("client_overview", {"client": "demo-grocery"}),
        PlannedQuery("application_services", {"application": "storefront"}),
        PlannedQuery("service_owner", {"service": "orders-service"}),
        PlannedQuery("api_consumers", {"api": "payments-api"}),
        PlannedQuery("event_flow", {"event": "order.created"}),
        PlannedQuery("service_product_context", {"service": "driver-service"}),
        PlannedQuery("relation_path", {"start": "tracking-service", "end": "driver-service"}),
        PlannedQuery("describe", {"entity": "payments-service"}),
        PlannedQuery("obsolete_documents", {}),
    ]
    facts = run_graph_queries(sample_graph, queries)
    assert [f.id for f in facts] == [f"K{i}" for i in range(1, 10)]
    assert all(f.found for f in facts)


def test_a_plan_can_list_every_team_and_the_result_is_evidence(sample_graph: KnowledgeGraph) -> None:
    fact = run_graph_queries(sample_graph, [PlannedQuery("list_entities", {"type": "team"})])[0]

    assert fact.found is True and fact.id == "K1"
    assert "orders-team" in fact.text and "driver-team" in fact.text
    assert fact.sources  # cited evidence


def test_a_team_overview_is_a_fact_with_the_leads(sample_graph: KnowledgeGraph) -> None:
    fact = run_graph_queries(sample_graph, [PlannedQuery("team_overview", {"team": "orders-team"})])[0]

    assert "orders-service" in fact.text and "Tomás Aguirre" in fact.text
