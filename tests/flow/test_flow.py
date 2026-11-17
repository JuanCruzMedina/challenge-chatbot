"""Spec: every question goes through one centralized pipeline; answers are plain data."""
from __future__ import annotations

import json
import os

import pytest

from ecosystem_assistant.knowledge.flow.answer import INSUFFICIENT_MESSAGE
from ecosystem_assistant.knowledge.flow.graph import InformationalFlow, default_min_score
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from ecosystem_assistant.llm.port import LLMOutputError, LLMUnavailableError
from ecosystem_assistant.llm.scripted import ScriptedLLM

STAGES = ["plan", "graph_queries", "document_search", "answer", "check"]
OWNER_PLAN = {"graph_queries": [{"method": "service_owner", "arguments": {"service": "tracking-service"}}],
              "filters": {}, "include_obsolete": False}
EMPTY_PLAN = {"graph_queries": [], "filters": {}, "include_obsolete": False}
COMBINED = "Who owns the service that tracks vehicles, and what should I do when a vehicle disappears from the map?"


def flow(graph: KnowledgeGraph, index: RetrievalIndex, script: list, min_score: float = 0.0) -> tuple[InformationalFlow, ScriptedLLM]:
    llm = ScriptedLLM(script)
    return InformationalFlow(graph, index, llm, min_score=min_score), llm


def test_the_stages_run_in_order_and_are_all_reported(sample_graph, sample_index) -> None:
    f, _ = flow(sample_graph, sample_index, [OWNER_PLAN, {"answer": "tracking-team [K1]", "citations": ["K1"]}])

    answer = f.ask(COMBINED)

    assert [step.stage for step in answer.trace] == STAGES
    assert all(step.outcome for step in answer.trace)


def test_a_graph_only_plan_still_searches_the_documents(sample_graph, sample_index) -> None:
    f, llm = flow(sample_graph, sample_index, [OWNER_PLAN, {"answer": "ok [K1]", "citations": ["K1"]}])

    answer = f.ask(COMBINED)

    search = next(s for s in answer.trace if s.stage == "document_search")
    assert search.details["kept"] > 0
    assert "[D1]" in llm.calls[1].user  # the passages reached the model next to the graph fact
    assert "[K1]" in llm.calls[1].user


def test_a_combined_question_uses_and_cites_both_sources(sample_graph, sample_index) -> None:
    f, _ = flow(sample_graph, sample_index, [
        OWNER_PLAN, {"answer": "tracking-team owns it [K1]. Follow the runbook [D1].", "citations": ["K1", "D1"]}])

    answer = f.ask(COMBINED)

    assert answer.status == "answered" and answer.grounded is True
    assert {c.kind for c in answer.citations} == {"graph", "document"}
    graph_citation = next(c for c in answer.citations if c.kind == "graph")
    assert graph_citation.sources == ["repos/tracking-service/service.yaml"]


def test_an_answer_serializes_to_json_with_every_field(sample_graph, sample_index) -> None:
    f, _ = flow(sample_graph, sample_index, [OWNER_PLAN, {"answer": "tracking-team [K1]", "citations": ["K1"]}])

    data = f.ask(COMBINED).to_dict()

    assert json.loads(json.dumps(data)) == data
    assert {"question", "text", "status", "grounded", "citations", "trace"} <= set(data)
    assert data["question"] == COMBINED and data["status"] == "answered"
    assert [s["stage"] for s in data["trace"]] == STAGES


def test_no_evidence_gives_insufficient_evidence_and_the_model_is_called_only_to_plan(sample_graph, sample_index) -> None:
    f, llm = flow(sample_graph, sample_index, [EMPTY_PLAN], min_score=1.01)

    answer = f.ask("What is the capital of France?")

    assert answer.status == "insufficient_evidence" and answer.grounded is False
    assert answer.text == INSUFFICIENT_MESSAGE and answer.citations == []
    assert len(llm.calls) == 1 and llm.calls[0].kind == "json"
    assert [s.stage for s in answer.trace] == STAGES
    assert next(s for s in answer.trace if s.stage == "answer").outcome == "skipped"


def test_weak_passages_never_reach_the_model(sample_graph, sample_index) -> None:
    f, llm = flow(sample_graph, sample_index, [OWNER_PLAN, {"answer": "tracking-team [K1]", "citations": ["K1"]}],
                  min_score=1.01)

    answer = f.ask(COMBINED)

    assert answer.status == "answered"
    assert "[K1]" in llm.calls[1].user and "[D1]" not in llm.calls[1].user
    search = next(s for s in answer.trace if s.stage == "document_search")
    assert search.details["kept"] == 0 and search.details["below_threshold"] > 0


def test_a_plan_that_fails_twice_falls_back_to_a_document_search_and_is_degraded(sample_graph, sample_index) -> None:
    f, llm = flow(sample_graph, sample_index, [
        LLMOutputError("bad"), LLMOutputError("worse"), {"answer": "see the runbook [D1]", "citations": ["D1"]}])

    answer = f.ask(COMBINED)

    assert answer.status == "degraded"
    assert answer.text == "see the runbook [D1]" and answer.grounded is True
    plan = next(s for s in answer.trace if s.stage == "plan")
    assert plan.outcome == "degraded" and plan.details["attempts"] == 2
    assert next(s for s in answer.trace if s.stage == "graph_queries").details["executed"] == []
    assert len(llm.calls) == 3


def test_a_failing_answer_falls_back_to_the_evidence_and_is_degraded(sample_graph, sample_index) -> None:
    f, _ = flow(sample_graph, sample_index, [OWNER_PLAN, LLMOutputError("bad"), LLMOutputError("worse")])

    answer = f.ask(COMBINED)

    assert answer.status == "degraded" and answer.grounded is False
    assert "tracking-team" in answer.text and "repos/" in answer.text
    assert answer.citations  # the sources are still shown


def test_an_unreachable_model_is_an_error_not_a_silent_fallback(sample_graph, sample_index) -> None:
    f, _ = flow(sample_graph, sample_index, [LLMUnavailableError("Cannot reach Ollama at http://x. `ollama serve`.")])
    with pytest.raises(LLMUnavailableError, match="ollama serve"):
        f.ask(COMBINED)


def test_dropped_plan_items_and_removed_citations_appear_in_the_trace(sample_graph, sample_index) -> None:
    plan = {"graph_queries": [{"method": "delete_everything", "arguments": {}},
                              {"method": "service_owner", "arguments": {"service": "tracking-service"}}],
            "filters": {"client": "Imaginary Corp"}}
    f, _ = flow(sample_graph, sample_index, [plan, {"answer": "ok [K1] [D99]", "citations": ["K1", "D99"]}])

    answer = f.ask(COMBINED)

    plan_step = next(s for s in answer.trace if s.stage == "plan")
    assert len(plan_step.details["dropped"]) == 2
    assert next(s for s in answer.trace if s.stage == "check").details["removed"] == ["D99"]


def test_the_plan_filters_and_the_obsolete_flag_reach_the_search(sample_graph, sample_index) -> None:
    plan = {"graph_queries": [], "filters": {"client": "Demo Grocery"}, "include_obsolete": True}
    f, _ = flow(sample_graph, sample_index, [plan, {"answer": "x [D1]", "citations": ["D1"]}])

    answer = f.ask("What is the process for order problems?")

    search = next(s for s in answer.trace if s.stage == "document_search")
    assert search.details["filters"] == {"client": "demo-grocery"} and search.details["include_obsolete"] is True


def test_a_blank_question_gets_no_model_call(sample_graph, sample_index) -> None:
    f, llm = flow(sample_graph, sample_index, [])
    answer = f.ask("   ")
    assert answer.status == "insufficient_evidence" and llm.calls == []


def test_the_default_minimum_score_depends_on_the_embedder(sample_graph, sample_index) -> None:
    assert default_min_score("hashing") >= 0.0
    with pytest.raises(ValueError, match="calibrat"):
        default_min_score("some-other-embedder")
    assert InformationalFlow(sample_graph, sample_index, ScriptedLLM()).min_score == default_min_score("hashing")


def test_graph_tracing_to_an_external_service_is_forced_off() -> None:
    assert os.environ["LANGSMITH_TRACING"] == "false" and os.environ["LANGCHAIN_TRACING_V2"] == "false"
