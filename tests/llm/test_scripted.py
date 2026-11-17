"""Spec: the scripted model replays responses, records calls and fails clearly when it runs out."""
from __future__ import annotations

import pytest

from ecosystem_assistant.llm.port import LLMError, LLMOutputError, LLMUnavailableError
from ecosystem_assistant.llm.scripted import Call, ScriptedLLM, ScriptExhaustedError


def test_responses_are_replayed_in_order_and_the_script_can_run_out() -> None:
    llm = ScriptedLLM(["first", "second"])

    assert llm.complete("sys", "one") == "first"
    assert llm.complete("sys", "two") == "second"
    with pytest.raises(ScriptExhaustedError) as exc:
        llm.complete("sys", "three")

    assert "ran out" in str(exc.value)
    assert isinstance(exc.value, LLMError)


def test_every_call_is_recorded_with_its_prompts_and_schema() -> None:
    llm = ScriptedLLM(["text", {"a": 1}])
    schema = {"type": "object"}

    llm.complete("the system", "the user")
    llm.complete_json("json system", "json user", schema)

    assert llm.calls == [
        Call(kind="complete", system="the system", user="the user", schema=None),
        Call(kind="json", system="json system", user="json user", schema=schema),
    ]


def test_json_responses_can_be_objects_or_json_text() -> None:
    llm = ScriptedLLM([{"x": 1}, '{"y": 2}'])
    assert llm.complete_json("s", "u", {}) == {"x": 1}
    assert llm.complete_json("s", "u", {}) == {"y": 2}


@pytest.mark.parametrize("bad", ["not json at all", "[1, 2, 3]", '"just a string"', ""])
def test_a_response_that_is_not_a_json_object_is_an_output_error(bad: str) -> None:
    with pytest.raises(LLMOutputError):
        ScriptedLLM([bad]).complete_json("s", "u", {})


def test_a_response_that_is_an_exception_is_raised() -> None:
    llm = ScriptedLLM([LLMUnavailableError("the model is down"), "after"])
    with pytest.raises(LLMUnavailableError, match="the model is down"):
        llm.complete("s", "u")
    assert llm.complete("s", "u") == "after"  # the script goes on after the failure


def test_a_responder_function_can_answer_instead_of_a_list() -> None:
    llm = ScriptedLLM(responder=lambda call: {"echo": call.user})
    assert llm.complete_json("s", "hello", {}) == {"echo": "hello"}
    assert llm.complete_json("s", "again", {}) == {"echo": "again"}
    assert len(llm.calls) == 2


def test_the_name_identifies_the_provider() -> None:
    assert ScriptedLLM().name == "scripted"
