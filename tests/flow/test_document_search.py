"""Spec: the document search always runs, honors the plan's filters and obsolete flag, and drops weak passages."""
from __future__ import annotations

import shutil
from pathlib import Path

from ecosystem_assistant.actions.tools.documents import set_obsolete
from ecosystem_assistant.actions.workspace import Workspace
from ecosystem_assistant.knowledge.flow.evidence import (
    Fact,
    build_evidence,
    has_evidence,
    search_documents,
)
from ecosystem_assistant.knowledge.flow.plan import Plan
from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from tests.data.helpers import SAMPLE

QUESTION = "what should I do when a vehicle disappears from the map?"


def test_the_search_runs_even_with_an_empty_plan(sample_index: RetrievalIndex) -> None:
    result = search_documents(sample_index, QUESTION, Plan(), min_score=0.0)

    assert result.passages and result.passages[0].path == "repos/tracking-service/docs/runbook-missing-positions.md"
    assert [p.id for p in result.passages] == [f"D{i}" for i in range(1, len(result.passages) + 1)]
    first = result.passages[0]
    assert first.heading_path.startswith("Runbook: a vehicle disappears from the map")
    assert (first.client, first.service, first.status) == ("demo-logistics", "tracking-service", "current")
    assert 0.0 < first.score <= 1.0


def test_the_plan_filters_restrict_the_search(sample_index: RetrievalIndex) -> None:
    plan = Plan(filters={"client": "demo-logistics"})
    result = search_documents(sample_index, "who is on call", plan, min_score=0.0, k=5)
    assert result.passages and {p.client for p in result.passages} == {"demo-logistics"}

    by_service = search_documents(sample_index, "api", Plan(filters={"service": "orders-service"}), min_score=0.0)
    assert by_service.passages and {p.service for p in by_service.passages} == {"orders-service"}


def test_passages_below_the_minimum_score_are_dropped_and_counted(sample_index: RetrievalIndex) -> None:
    everything = search_documents(sample_index, QUESTION, Plan(), min_score=0.0, k=5)
    nothing = search_documents(sample_index, QUESTION, Plan(), min_score=1.01, k=5)

    assert len([p for p in everything.passages if not p.neighbour]) == 5 and everything.below_threshold == 0
    assert nothing.passages == [] and nothing.below_threshold == 5

    cut = everything.passages[2].score
    partial = search_documents(sample_index, QUESTION, Plan(), min_score=cut, k=5)
    assert all(p.score >= cut for p in partial.passages)
    assert len([p for p in partial.passages if not p.neighbour]) + partial.below_threshold == 5


def test_obsolete_documents_are_excluded_unless_the_plan_asks_for_them(tmp_path: Path) -> None:
    copy = tmp_path / "ecosystem"
    shutil.copytree(SAMPLE, copy)
    index = RetrievalIndex(tmp_path / "index", HashingEmbedder())
    set_obsolete(Workspace(root=copy, audit_file=tmp_path / "audit.jsonl"), "payments-service",
                 "docs/api-v1.md", "Replaced by v2", "docs/api-v2.md")
    index.sync(copy)
    question = "v1 does not support automatic retries after a failure"
    path = "repos/payments-service/docs/api-v1.md"

    default = search_documents(index, question, Plan(), min_score=0.0, k=10)
    wanted = search_documents(index, question, Plan(include_obsolete=True), min_score=0.0, k=10)

    assert path not in {p.path for p in default.passages}
    marked = [p for p in wanted.passages if p.path == path]
    assert marked and {p.status for p in marked} == {"obsolete"}


def _passage_set(index: RetrievalIndex):
    return search_documents(index, QUESTION, Plan(), min_score=0.0, k=5).passages


def test_the_evidence_is_numbered_and_formatted_for_the_model(sample_index: RetrievalIndex) -> None:
    fact = Fact("K1", "service_owner", {"service": "tracking-service"}, True, '{"team":"tracking-team"}', ["a.yaml"])
    passages = _passage_set(sample_index)

    evidence = build_evidence([fact], passages)

    assert evidence.text.index("[K1]") < evidence.text.index("[D1]")
    assert "service_owner" in evidence.text and "tracking-team" in evidence.text
    assert passages[0].path in evidence.text and passages[0].heading_path in evidence.text
    assert evidence.passages == passages and evidence.dropped_passages == 0


def test_the_evidence_cap_drops_the_lowest_scoring_passages_first(sample_index: RetrievalIndex) -> None:
    passages = _passage_set(sample_index)
    one_passage = build_evidence([], passages[:1]).text

    capped = build_evidence([], passages, max_chars=len(one_passage) + 40)

    assert [p.id for p in capped.passages] == ["D1"]
    assert capped.dropped_passages == len(passages) - 1
    assert len(capped.text) <= len(one_passage) + 40


def test_there_is_evidence_when_a_fact_was_found_or_a_passage_survived(sample_index: RetrievalIndex) -> None:
    missing = Fact("K1", "service_owner", {}, False, "not found", [])
    found = Fact("K2", "service_owner", {}, True, "{}", [])
    passages = _passage_set(sample_index)

    assert has_evidence([], []) is False
    assert has_evidence([missing], []) is False
    assert has_evidence([found], []) is True
    assert has_evidence([missing], passages) is True
