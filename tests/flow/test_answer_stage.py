"""Spec: the model gets numbered evidence and writes a JSON answer; invalid output is retried once."""
from __future__ import annotations

import pytest

from ecosystem_assistant.knowledge.flow.answer import INSUFFICIENT_MESSAGE, write_answer
from ecosystem_assistant.knowledge.flow.prompts import ANSWER_SCHEMA
from ecosystem_assistant.llm.port import LLMError, LLMOutputError, LLMUnavailableError
from ecosystem_assistant.llm.scripted import ScriptedLLM

QUESTION = "Who consumes the payments API?"
EVIDENCE = "GRAPH FACTS (from the knowledge graph)\n\n[K1] api_consumers(api=payments api): {\"consumers\":[]}"
GOOD = {"answer": "orders-service consumes it [K1].", "citations": ["K1"]}


def test_the_model_receives_the_question_and_the_numbered_evidence_and_the_schema() -> None:
    llm = ScriptedLLM([GOOD])

    draft = write_answer(llm, QUESTION, EVIDENCE)

    call = llm.calls[0]
    assert call.kind == "json" and call.schema == ANSWER_SCHEMA
    assert QUESTION in call.user and "[K1]" in call.user and EVIDENCE in call.user
    assert "only" in call.system.lower() and "cite" in call.system.lower()
    assert (draft.text, draft.citation_ids, draft.attempts, draft.failed) == (GOOD["answer"], ["K1"], 1, False)


def test_the_insufficient_message_says_that_nothing_was_found() -> None:
    assert "could not find" in INSUFFICIENT_MESSAGE.lower()


def test_invalid_output_is_retried_once_with_the_error_in_the_prompt() -> None:
    llm = ScriptedLLM([LLMOutputError("The model did not return valid JSON (oops)"), GOOD])

    draft = write_answer(llm, QUESTION, EVIDENCE)

    assert len(llm.calls) == 2 and draft.attempts == 2 and draft.failed is False
    assert "not valid" in llm.calls[1].user and "oops" in llm.calls[1].user and EVIDENCE in llm.calls[1].user


def test_two_failures_leave_a_failed_draft_with_the_last_error() -> None:
    llm = ScriptedLLM([LLMOutputError("first"), LLMOutputError("second")])

    draft = write_answer(llm, QUESTION, EVIDENCE)

    assert len(llm.calls) == 2 and draft.failed is True and "second" in draft.error
    assert draft.text == "" and draft.citation_ids == []


@pytest.mark.parametrize("bad", [
    {"answer": 5, "citations": []},
    {"answer": "text", "citations": "K1"},
    {"citations": ["K1"]},
    {"answer": "   ", "citations": []},
    {"answer": "text", "citations": [1, 2]},
])
def test_a_json_object_with_the_wrong_shape_counts_as_invalid_output(bad: dict) -> None:
    llm = ScriptedLLM([bad, bad])
    draft = write_answer(llm, QUESTION, EVIDENCE)
    assert draft.failed is True and len(llm.calls) == 2


def test_another_model_failure_is_also_retried_once() -> None:
    llm = ScriptedLLM([LLMError("the server returned an error"), GOOD])
    assert write_answer(llm, QUESTION, EVIDENCE).attempts == 2


def test_an_unreachable_model_propagates_without_a_retry() -> None:
    llm = ScriptedLLM([LLMUnavailableError("Cannot reach Ollama. Start it with `ollama serve`.")])
    with pytest.raises(LLMUnavailableError):
        write_answer(llm, QUESTION, EVIDENCE)
    assert len(llm.calls) == 1
