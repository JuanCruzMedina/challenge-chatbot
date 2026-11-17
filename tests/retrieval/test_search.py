"""Spec: search returns cited chunks, filtered by scope, bounded, deterministic and plain data."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ecosystem_assistant.actions.tools.documents import set_obsolete
from ecosystem_assistant.actions.workspace import Workspace
from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from tests.data.helpers import SAMPLE

TRACKING_RUNBOOK = "repos/tracking-service/docs/runbook-missing-positions.md"


@pytest.fixture(scope="module")
def sample_index(tmp_path_factory: pytest.TempPathFactory) -> RetrievalIndex:
    """An index of the committed data with the offline embedder, shared by the module (read-only use)."""
    index = RetrievalIndex(tmp_path_factory.mktemp("index"), HashingEmbedder())
    index.sync(SAMPLE)
    return index


def test_a_question_finds_the_document_that_answers_it(sample_index: RetrievalIndex) -> None:
    hits = sample_index.search("what should I do when a vehicle disappears from the map?")

    top = hits[0]
    assert top.citation.path == TRACKING_RUNBOOK
    assert top.citation.title == "Runbook: a vehicle disappears from the map"
    assert top.citation.heading_path.startswith("Runbook: a vehicle disappears from the map")
    assert (top.citation.service, top.citation.client, top.citation.status) == (
        "tracking-service", "demo-logistics", "current")
    assert top.text.startswith(top.citation.heading_path)


def test_results_can_be_limited_to_a_client(sample_index: RetrievalIndex) -> None:
    question = "who is on call and who to escalate to"
    unrestricted = {h.citation.client for h in sample_index.search(question, k=20)}
    logistics = sample_index.search(question, k=20, client="demo-logistics")

    assert {"demo-grocery", "demo-logistics"} <= unrestricted
    assert logistics and {h.citation.client for h in logistics} == {"demo-logistics"}


def test_results_can_be_limited_to_an_application_and_to_a_service(sample_index: RetrievalIndex) -> None:
    by_app = sample_index.search("api endpoints and rules", k=20, application="fleet-tracker")
    assert by_app and {h.citation.service for h in by_app} <= {"tracking-service", "routing-service"}

    by_service = sample_index.search("api endpoints and rules", k=20, service="orders-service")
    assert by_service and {h.citation.service for h in by_service} == {"orders-service"}


def test_filters_combine(sample_index: RetrievalIndex) -> None:
    hits = sample_index.search("runbook", k=20, client="demo-grocery", service="payments-service")
    assert hits and {(h.citation.client, h.citation.service) for h in hits} == {("demo-grocery", "payments-service")}
    assert sample_index.search("runbook", k=20, client="demo-logistics", service="payments-service") == []


def test_obsolete_documents_are_hidden_unless_requested(tmp_path: Path) -> None:
    copy = tmp_path / "ecosystem"
    shutil.copytree(SAMPLE, copy)
    index = RetrievalIndex(tmp_path / "index", HashingEmbedder())
    index.sync(copy)
    question = "v1 does not support automatic retries after a failure"
    path = "repos/payments-service/docs/api-v1.md"
    assert any(h.citation.path == path for h in index.search(question, k=20))

    set_obsolete(Workspace(root=copy, audit_file=tmp_path / "audit.jsonl"), "payments-service",
                 "docs/api-v1.md", "Replaced by v2", "docs/api-v2.md")
    index.sync(copy)

    assert not any(h.citation.path == path for h in index.search(question, k=20))
    with_obsolete = [h for h in index.search(question, k=20, include_obsolete=True) if h.citation.path == path]
    assert with_obsolete and {h.citation.status for h in with_obsolete} == {"obsolete"}


@pytest.mark.parametrize(("k", "expected"), [(100, 20), (20, 20), (7, 7), (0, 0), (-3, 0)])
def test_the_number_of_results_is_bounded(sample_index: RetrievalIndex, k: int, expected: int) -> None:
    assert len(sample_index.search("service", k=k)) == expected


def test_the_default_number_of_results_is_five(sample_index: RetrievalIndex) -> None:
    assert len(sample_index.search("service")) == 5


@pytest.mark.parametrize("question", ["", "   ", "\n\t"])
def test_an_empty_question_returns_nothing_and_raises_nothing(sample_index: RetrievalIndex, question: str) -> None:
    assert sample_index.search(question) == []


def test_searching_an_empty_index_returns_nothing(tmp_path: Path) -> None:
    assert RetrievalIndex(tmp_path / "empty", HashingEmbedder()).search("anything at all") == []


def test_scores_are_between_zero_and_one_best_first_with_stable_ties(sample_index: RetrievalIndex) -> None:
    hits = sample_index.search("payments", k=20)
    scores = [h.score for h in hits]

    assert all(0.0 <= s <= 1.0 for s in scores)
    assert scores == sorted(scores, reverse=True)
    keys = [(-h.score, h.citation.path, h.text) for h in hits]
    assert keys == sorted(keys)
    assert sample_index.search("payments", k=20) == hits  # the same question gives the same answer


def test_results_serialize_to_json_with_the_citation_fields(sample_index: RetrievalIndex) -> None:
    data = [h.to_dict() for h in sample_index.search("payments retries", k=3)]

    assert json.loads(json.dumps(data)) == data
    for item in data:
        assert set(item) == {"text", "score", "citation"}
        assert set(item["citation"]) == {
            "title", "heading_path", "path", "scope", "service", "application", "client", "status"}
