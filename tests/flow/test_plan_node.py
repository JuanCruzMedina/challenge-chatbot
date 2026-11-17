"""Spec: invalid plans are retried once and then fall back to a document search alone."""
from __future__ import annotations

import pytest

from ecosystem_assistant.knowledge.flow.catalog import CATALOG, PLAN_SCHEMA
from ecosystem_assistant.knowledge.flow.plan import make_plan
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from ecosystem_assistant.llm.port import LLMOutputError, LLMUnavailableError
from ecosystem_assistant.llm.scripted import ScriptedLLM

QUESTION = "Who consumes the payments API?"
GOOD = {"graph_queries": [{"method": "api_consumers", "arguments": {"api": "payments api"}}],
        "filters": {}, "include_obsolete": False}


def test_the_plan_is_asked_as_json_with_the_schema_and_the_catalog_in_the_prompt(sample_graph: KnowledgeGraph) -> None:
    llm = ScriptedLLM([GOOD])

    outcome = make_plan(llm, sample_graph, QUESTION)

    call = llm.calls[0]
    assert call.kind == "json" and call.schema == PLAN_SCHEMA
    assert all(method in call.system for method in CATALOG)
    assert "orders-service" in call.system and "demo-logistics" in call.system  # known names help small models
    assert QUESTION in call.user
    assert [q.method for q in outcome.plan.graph_queries] == ["api_consumers"]
    assert outcome.degraded is False and outcome.attempts == 1


def test_an_invalid_first_answer_is_retried_once_with_the_error_in_the_prompt(sample_graph: KnowledgeGraph) -> None:
    llm = ScriptedLLM([LLMOutputError("The model did not return valid JSON (Expecting value)"), GOOD])

    outcome = make_plan(llm, sample_graph, QUESTION)

    assert len(llm.calls) == 2 and outcome.attempts == 2
    assert "not valid" in llm.calls[1].user and "Expecting value" in llm.calls[1].user
    assert QUESTION in llm.calls[1].user
    assert [q.method for q in outcome.plan.graph_queries] == ["api_consumers"]
    assert outcome.degraded is False


def test_two_invalid_answers_fall_back_to_a_document_search_alone(sample_graph: KnowledgeGraph) -> None:
    llm = ScriptedLLM([LLMOutputError("bad one"), LLMOutputError("bad two")])

    outcome = make_plan(llm, sample_graph, QUESTION)

    assert len(llm.calls) == 2  # exactly one retry, never more
    assert outcome.plan.graph_queries == [] and outcome.plan.filters == {}
    assert outcome.degraded is True and outcome.attempts == 2
    assert "bad two" in outcome.error


def test_an_unreachable_model_is_not_hidden_by_the_fallback(sample_graph: KnowledgeGraph) -> None:
    llm = ScriptedLLM([LLMUnavailableError("Cannot reach Ollama at http://x. Start it with `ollama serve`.")])
    with pytest.raises(LLMUnavailableError, match="ollama serve"):
        make_plan(llm, sample_graph, QUESTION)
    assert len(llm.calls) == 1  # no retry against a model that is down


def test_a_plan_with_bad_items_is_not_retried_but_its_bad_items_are_dropped(sample_graph: KnowledgeGraph) -> None:
    llm = ScriptedLLM([{"graph_queries": [{"method": "nope", "arguments": {}}], "filters": {}}])
    outcome = make_plan(llm, sample_graph, QUESTION)
    assert len(llm.calls) == 1 and outcome.degraded is False
    assert outcome.plan.dropped
