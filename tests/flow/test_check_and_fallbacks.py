"""Spec: citations are validated and resolved to sources; a failing model gives an evidence-only answer."""
from __future__ import annotations

import pytest

from ecosystem_assistant.knowledge.flow.answer import check_citations, evidence_only_text, run_answer_stage
from ecosystem_assistant.knowledge.flow.evidence import Evidence, Fact, Passage, build_evidence
from ecosystem_assistant.llm.port import LLMError, LLMOutputError, LLMUnavailableError
from ecosystem_assistant.llm.scripted import ScriptedLLM

FACT = Fact("K1", "service_owner", {"service": "tracking-service"}, True, '{"team":"tracking-team"}',
            ["repos/tracking-service/service.yaml", "company.yaml"])
NOT_FOUND = Fact("K2", "service_owner", {"service": "ordres-service"}, False, "Not found: 'ordres-service'.", [])
PASSAGES = [
    Passage(f"D{i}", f"Runbook > Step {i}\n\ntext {i}", 0.9 - i / 10, f"repos/x/docs/runbook-{i}.md",
            f"Runbook > Step {i}", "Runbook", "demo-logistics", "tracking-service", "current")
    for i in (1, 2, 3)
]


def evidence() -> Evidence:
    return build_evidence([FACT, NOT_FOUND], PASSAGES)


def test_valid_citations_are_resolved_to_their_sources() -> None:
    result = check_citations("It is owned by tracking-team [K1] and the runbook says so [D2].", ["K1", "D2"],
                             [FACT], PASSAGES)

    assert [c.id for c in result.citations] == ["K1", "D2"]
    graph, document = result.citations
    assert graph.kind == "graph" and graph.sources == ["repos/tracking-service/service.yaml", "company.yaml"]
    assert "service_owner" in graph.label
    assert document.kind == "document" and document.sources == ["repos/x/docs/runbook-2.md"]
    assert "Runbook > Step 2" in document.label
    assert result.grounded is True and result.removed == []


def test_invented_citations_are_removed_and_recorded() -> None:
    result = check_citations("Answer [K1] [D9].", ["K1", "D9", "X5"], [FACT], PASSAGES)

    assert [c.id for c in result.citations] == ["K1"]
    assert sorted(result.removed) == ["D9", "X5"]
    assert result.grounded is True


def test_citations_written_inline_but_missing_from_the_list_are_found_and_checked() -> None:
    result = check_citations("It is tracking-team [K1], also see [D3] and [D7].", ["K1"], [FACT], PASSAGES)
    assert [c.id for c in result.citations] == ["K1", "D3"]
    assert result.removed == ["D7"]


def test_odd_citation_formats_are_normalized_and_duplicates_collapse() -> None:
    result = check_citations("text", ["[K1]", "k1", "D2.", " d2 "], [FACT], PASSAGES)
    assert [c.id for c in result.citations] == ["K1", "D2"] and result.removed == []


def test_an_answer_with_no_valid_citation_is_not_grounded() -> None:
    result = check_citations("It is owned by someone.", ["D9"], [FACT], PASSAGES)
    assert result.citations == [] and result.grounded is False and result.removed == ["D9"]
    assert check_citations("No citations at all.", [], [FACT], PASSAGES).grounded is False


def test_the_evidence_only_text_lists_the_facts_and_the_best_passages_with_their_sources() -> None:
    text = evidence_only_text([FACT, NOT_FOUND], PASSAGES)

    assert "service_owner" in text and "tracking-team" in text
    assert "repos/x/docs/runbook-1.md" in text and "Runbook > Step 1" in text
    assert text == evidence_only_text([FACT, NOT_FOUND], PASSAGES)  # deterministic
    assert "ordres-service" not in text  # a fact that found nothing is not presented as an answer


def test_a_good_answer_is_checked_and_returned_as_answered() -> None:
    llm = ScriptedLLM([{"answer": "tracking-team owns it [K1].", "citations": ["K1", "D9"]}])

    result = run_answer_stage(llm, "Who owns tracking?", evidence())

    assert result.status == "answered" and result.grounded is True
    assert result.text == "tracking-team owns it [K1]."
    assert [c.id for c in result.citations] == ["K1"] and result.removed == ["D9"]


def test_an_ungrounded_answer_is_still_answered_but_flagged() -> None:
    llm = ScriptedLLM([{"answer": "Probably the platform team.", "citations": []}])
    result = run_answer_stage(llm, "Who owns tracking?", evidence())
    assert result.status == "answered" and result.grounded is False and result.text == "Probably the platform team."


def test_a_model_that_fails_twice_gives_the_evidence_only_answer_as_degraded() -> None:
    llm = ScriptedLLM([LLMOutputError("bad"), LLMOutputError("worse")])

    result = run_answer_stage(llm, "Who owns tracking?", evidence())

    assert len(llm.calls) == 2
    assert result.status == "degraded" and result.grounded is False
    assert "tracking-team" in result.text and "repos/x/docs/runbook-1.md" in result.text
    assert [c.id for c in result.citations][:2] == ["K1", "D1"]  # the sources are still visible
    assert "worse" in result.error


def test_a_failing_model_that_recovers_on_the_retry_is_answered() -> None:
    llm = ScriptedLLM([LLMError("transient"), {"answer": "tracking-team [K1]", "citations": ["K1"]}])
    result = run_answer_stage(llm, "Who owns tracking?", evidence())
    assert result.status == "answered" and result.attempts == 2


def test_an_unreachable_model_is_never_replaced_silently() -> None:
    llm = ScriptedLLM([LLMUnavailableError("Cannot reach Ollama. Start it with `ollama serve`.")])
    with pytest.raises(LLMUnavailableError):
        run_answer_stage(llm, "Who owns tracking?", evidence())
