"""Spec: a cut graph answer is marked, and no catalog query is cut on the sample data (guard-graph-fact-size)."""
from __future__ import annotations

from ecosystem_assistant.knowledge.flow.catalog import CATALOG
from ecosystem_assistant.knowledge.flow.evidence import FACT_MAX_CHARS, run_graph_queries
from ecosystem_assistant.knowledge.flow.plan import PlannedQuery

# One representative call per catalog query. A query added to the catalog needs a line here: if its answer is long,
# make it compact (see teams_overview) instead of letting the flow cut it.
CASES: dict[str, dict[str, str]] = {
    "client_overview": {"client": "demo-grocery"},
    "application_services": {"application": "storefront"},
    "service_owner": {"service": "orders-service"},
    "api_consumers": {"api": "payments-api"},
    "event_flow": {"event": "order.created"},
    "service_product_context": {"service": "orders-service"},
    "relation_path": {"start": "orders-service", "end": "driver-service"},
    "describe": {"entity": "orders-service"},
    "obsolete_documents": {},
    "list_entities": {"type": "documents"},
    "team_overview": {"team": "orders-team"},
    "teams_overview": {},
}


def test_the_guard_has_a_case_for_every_catalog_query() -> None:
    assert sorted(CASES) == sorted(CATALOG), "add a representative case for the new query"


def test_no_catalog_query_is_cut_on_the_sample_data(sample_graph) -> None:
    for method, arguments in CASES.items():
        fact = run_graph_queries(sample_graph, [PlannedQuery(method, arguments)])[0]
        assert fact.found, method
        assert fact.truncated is False, f"{method} {arguments} is {len(fact.text)} characters (cap {FACT_MAX_CHARS})"


def test_the_longest_known_answers_fit_with_the_current_cap(sample_graph) -> None:
    lengths = {m: len(run_graph_queries(sample_graph, [PlannedQuery(m, a)])[0].text) for m, a in CASES.items()}
    assert lengths["describe"] > 1500 and lengths["list_entities"] > 1500   # they were cut at the old cap
    assert max(lengths.values()) <= FACT_MAX_CHARS


def test_a_cut_fact_is_marked(sample_graph) -> None:
    fact = run_graph_queries(sample_graph, [PlannedQuery("describe", {"entity": "orders-service"})], max_chars=120)[0]
    assert fact.truncated is True and fact.text.endswith("…[truncated]")


def test_the_trace_lists_the_cut_facts(sample_graph, sample_index, monkeypatch) -> None:
    from ecosystem_assistant.knowledge.flow import nodes
    from tests.flow.test_flow import flow

    real = nodes.run_graph_queries
    monkeypatch.setattr(nodes, "run_graph_queries", lambda graph, queries: real(graph, queries, max_chars=60))
    plan = {"graph_queries": [{"method": "describe", "arguments": {"entity": "orders-service"}}]}
    f, _ = flow(sample_graph, sample_index, [plan, {"answer": "ok [K1]", "citations": ["K1"]}])

    answer = f.ask("What is orders-service related to?")

    step = next(s for s in answer.trace if s.stage == "graph_queries")
    assert step.details["executed"][0]["truncated"] is True
