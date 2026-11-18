"""Spec: the best document is completed with its other sections (add-neighbour-sections)."""
from __future__ import annotations

from ecosystem_assistant.knowledge.flow.answer import passage_info
from ecosystem_assistant.knowledge.flow.evidence import MAX_NEIGHBOURS, search_documents
from ecosystem_assistant.knowledge.flow.plan import Plan
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex

RUNBOOK = "repos/catalog-service/docs/runbook-stale-prices.md"
SYMPTOM = "A customer sees a price different from the one the commercial team loaded."


def _search(index: RetrievalIndex, question: str = SYMPTOM, min_score: float = 0.0, k: int = 1):
    return search_documents(index, question, Plan(), min_score=min_score, k=k)


def test_the_steps_of_a_runbook_come_with_its_symptom(sample_index: RetrievalIndex) -> None:
    result = _search(sample_index)

    assert result.passages[0].path == RUNBOOK and not result.passages[0].neighbour
    headings = [p.heading_path for p in result.passages if p.neighbour]
    assert any(h.endswith("Diagnosis") for h in headings) and any(h.endswith("Fix") for h in headings)
    assert "cache" in " ".join(p.text for p in result.passages if p.neighbour)
    ranked = [p for p in result.passages if not p.neighbour]
    assert result.passages[:len(ranked)] == ranked, "neighbours come after the ranked passages"


def test_neighbours_come_only_from_the_best_document_without_repeats(sample_index: RetrievalIndex) -> None:
    result = _search(sample_index, "who is on call for the runbook of delayed emails", k=5)

    best = result.passages[0].path
    neighbours = [p for p in result.passages if p.neighbour]
    assert len(neighbours) <= MAX_NEIGHBOURS == 4
    assert {p.path for p in neighbours} <= {best}
    keys = [(p.path, p.heading_path) for p in result.passages]
    assert len(keys) == len(set(keys)), "a section ranked already is not added again"


def test_the_ids_continue_the_sequence(sample_index: RetrievalIndex) -> None:
    result = _search(sample_index)
    assert [p.id for p in result.passages] == [f"D{n}" for n in range(1, len(result.passages) + 1)]


def test_nothing_is_added_without_a_good_match(sample_index: RetrievalIndex) -> None:
    result = _search(sample_index, min_score=1.01)
    assert result.passages == []


def test_the_neighbour_mark_reaches_the_caller_facing_passage(sample_index: RetrievalIndex) -> None:
    result = _search(sample_index)
    infos = [passage_info(p) for p in result.passages]

    assert [i.neighbour for i in infos] == [p.neighbour for p in result.passages]
    assert any(i.neighbour for i in infos) and "neighbour" in infos[0].to_dict()
