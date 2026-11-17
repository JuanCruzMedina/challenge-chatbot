"""Spec: the model plans graph queries from a fixed catalog, and the plan is validated before anything runs."""
from __future__ import annotations

from typing import Any

from ecosystem_assistant.knowledge.flow.catalog import CATALOG, MAX_QUERIES
from ecosystem_assistant.knowledge.flow.plan import PlannedQuery, validate_plan
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph


def query(method: str, **arguments: Any) -> dict[str, Any]:
    return {"method": method, "arguments": arguments}


def reasons(plan) -> list[str]:
    return [d.reason for d in plan.dropped]


def test_a_valid_plan_is_kept_as_it_is(sample_graph: KnowledgeGraph) -> None:
    plan = validate_plan({"graph_queries": [query("api_consumers", api="payments api")],
                          "filters": {}, "include_obsolete": False}, sample_graph)

    assert plan.graph_queries == [PlannedQuery("api_consumers", {"api": "payments api"})]
    assert plan.dropped == [] and plan.cut == 0
    assert plan.filters == {} and plan.include_obsolete is False


def test_the_catalog_has_the_graph_questions_and_nothing_else() -> None:
    assert set(CATALOG) == {
        "client_overview", "application_services", "service_owner", "api_consumers", "event_flow",
        "service_product_context", "relation_path", "describe", "obsolete_documents",
        "list_entities", "team_overview",
    }
    assert CATALOG["list_entities"].required == ("type",)
    assert CATALOG["team_overview"].required == ("team",)
    assert CATALOG["relation_path"].required == ("start", "end")
    assert CATALOG["obsolete_documents"].required == ()
    assert MAX_QUERIES == 4


def test_an_unknown_method_is_dropped_with_a_reason_and_the_valid_ones_still_run(sample_graph: KnowledgeGraph) -> None:
    plan = validate_plan({"graph_queries": [
        query("delete_everything", target="all"),
        query("service_owner", service="orders-service"),
    ]}, sample_graph)

    assert [q.method for q in plan.graph_queries] == ["service_owner"]
    assert any("unknown method" in r and "delete_everything" in r for r in reasons(plan))


def test_a_missing_required_argument_is_dropped_naming_it(sample_graph: KnowledgeGraph) -> None:
    plan = validate_plan({"graph_queries": [query("service_owner"), query("relation_path", start="a")]}, sample_graph)

    assert plan.graph_queries == []
    assert any("service" in r and "missing" in r for r in reasons(plan))
    assert any("end" in r and "missing" in r for r in reasons(plan))


def test_an_extra_argument_is_dropped_naming_it(sample_graph: KnowledgeGraph) -> None:
    plan = validate_plan({"graph_queries": [query("service_owner", service="x", color="red")]}, sample_graph)
    assert plan.graph_queries == []
    assert any("unexpected" in r and "color" in r for r in reasons(plan))


def test_arguments_that_are_not_text_are_dropped(sample_graph: KnowledgeGraph) -> None:
    plan = validate_plan({"graph_queries": [query("service_owner", service=42), query("event_flow", event="")]},
                         sample_graph)
    assert plan.graph_queries == []
    assert len(plan.dropped) == 2


def test_entries_that_are_not_objects_are_dropped(sample_graph: KnowledgeGraph) -> None:
    plan = validate_plan({"graph_queries": ["service_owner orders-service", None, 7]}, sample_graph)
    assert plan.graph_queries == [] and len(plan.dropped) == 3


def test_a_plan_whose_queries_are_not_a_list_is_treated_as_empty_and_recorded(sample_graph: KnowledgeGraph) -> None:
    plan = validate_plan({"graph_queries": "service_owner"}, sample_graph)
    assert plan.graph_queries == [] and any("list" in r for r in reasons(plan))
    assert validate_plan({}, sample_graph).graph_queries == []


def test_more_than_four_queries_are_cut_and_the_cut_is_recorded(sample_graph: KnowledgeGraph) -> None:
    six = [query("service_owner", service=name) for name in
           ("orders-service", "payments-service", "catalog-service", "tracking-service", "routing-service",
            "driver-service")]
    plan = validate_plan({"graph_queries": six}, sample_graph)

    assert [q.arguments["service"] for q in plan.graph_queries] == [
        "orders-service", "payments-service", "catalog-service", "tracking-service"]
    assert plan.cut == 2
    assert sum("cut" in r for r in reasons(plan)) == 2


def test_invalid_queries_do_not_use_up_the_limit(sample_graph: KnowledgeGraph) -> None:
    bad = [query("nope") for _ in range(5)]
    good = [query("service_owner", service="orders-service")]
    plan = validate_plan({"graph_queries": bad + good}, sample_graph)
    assert len(plan.graph_queries) == 1 and plan.cut == 0


def test_a_query_without_arguments_is_valid_when_none_are_needed(sample_graph: KnowledgeGraph) -> None:
    plan = validate_plan({"graph_queries": [query("obsolete_documents")]}, sample_graph)
    assert [q.method for q in plan.graph_queries] == ["obsolete_documents"]


def test_filters_are_resolved_to_the_ids_the_index_uses(sample_graph: KnowledgeGraph) -> None:
    plan = validate_plan({"graph_queries": [], "filters": {
        "client": "Demo Grocery", "application": "fleet tracker", "service": "orders service"}}, sample_graph)
    assert plan.filters == {"client": "demo-grocery", "application": "fleet-tracker", "service": "orders-service"}
    assert plan.dropped == []


def test_a_filter_naming_something_unknown_is_dropped_and_recorded(sample_graph: KnowledgeGraph) -> None:
    plan = validate_plan({"graph_queries": [], "filters": {"client": "Imaginary Corp", "service": "orders-service",
                                                           "colour": "blue"}}, sample_graph)
    assert plan.filters == {"service": "orders-service"}
    assert any("client" in r and "Imaginary Corp" in r for r in reasons(plan))
    assert any("colour" in r for r in reasons(plan))


def test_a_filter_of_the_wrong_kind_is_not_accepted(sample_graph: KnowledgeGraph) -> None:
    plan = validate_plan({"filters": {"client": "orders-service"}}, sample_graph)  # a service named as a client
    assert plan.filters == {} and len(plan.dropped) == 1


def test_include_obsolete_defaults_to_false_and_only_a_real_boolean_counts(sample_graph: KnowledgeGraph) -> None:
    assert validate_plan({}, sample_graph).include_obsolete is False
    assert validate_plan({"include_obsolete": True}, sample_graph).include_obsolete is True
    assert validate_plan({"include_obsolete": "yes"}, sample_graph).include_obsolete is False


def test_every_catalog_method_exists_on_the_graph_and_is_described(sample_graph: KnowledgeGraph) -> None:
    from ecosystem_assistant.knowledge.flow.catalog import describe_catalog

    text = describe_catalog()
    for method in CATALOG:
        assert callable(getattr(sample_graph, method)), method
        assert method in text
