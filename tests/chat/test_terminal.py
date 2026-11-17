"""Spec: the terminal chat forwards and prints, keeps the conversation and survives model errors."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from ecosystem_assistant.agent.records import AgentReply, ToolCallRecord
from ecosystem_assistant.agent.settings import AgentModelError
from ecosystem_assistant.chat.terminal import run_chat
from ecosystem_assistant.llm.port import LLMUnavailableError


class FakeAgent:
    """Stands in for Agent: records what it receives and answers with the next scripted outcome."""

    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.received: list[list[Any]] = []

    async def chat(self, messages: Any) -> AgentReply:
        self.received.append(list(messages))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def reply(text: str, *tools: str) -> AgentReply:
    calls = [ToolCallRecord(name, {}, "ok", False) for name in tools]
    return AgentReply(text, calls, [AIMessage(text)])


def session(agent: FakeAgent, lines: list[str]) -> list[str]:
    """Run the loop with the given typed lines; return everything printed."""
    typed = iter(lines)

    def read(_prompt: str) -> str:
        try:
            return next(typed)
        except StopIteration:
            raise EOFError from None

    out: list[str] = []
    asyncio.run(run_chat(agent, read, out.append))
    return out


def test_a_reply_is_printed_with_the_tools_that_were_called() -> None:
    out = session(FakeAgent([reply("tracking-team owns it", "query_knowledge")]), ["who owns tracking?", "/exit"])

    text = "\n".join(out)
    assert "tracking-team owns it" in text
    assert any("query_knowledge" in line and "called" in line for line in out)


def test_a_turn_with_no_tool_prints_only_the_reply() -> None:
    out = session(FakeAgent([reply("Hello!")]), ["hi", "/exit"])

    assert [line for line in out if "Hello!" in line]
    assert not any("called" in line for line in out)


def test_the_second_turn_receives_the_first_question_and_its_reply() -> None:
    agent = FakeAgent([reply("first answer"), reply("second answer")])

    session(agent, ["first question", "second question", "/exit"])

    second = agent.received[1]
    assert [type(m) for m in second] == [HumanMessage, AIMessage, HumanMessage]
    assert [m.content for m in second] == ["first question", "first answer", "second question"]


@pytest.mark.parametrize("ending", [["/exit"], []])  # the command, or the end of the input
def test_the_loop_ends_on_exit_and_on_end_of_input(ending: list[str]) -> None:
    agent = FakeAgent([reply("ok")])
    session(agent, ["one", *ending])
    assert len(agent.received) == 1


def test_exit_is_not_sent_to_the_agent_and_blank_lines_are_skipped() -> None:
    agent = FakeAgent([reply("ok")])
    session(agent, ["", "   ", "real question", "/exit"])
    assert [m.content for m in agent.received[0]] == ["real question"]
    assert len(agent.received) == 1


# --- failures -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("error", [
    AgentModelError("Cannot reach the model server. Start it with `ollama serve`."),
    LLMUnavailableError("Cannot reach Ollama at http://x. Start it with `ollama serve`."),
])
def test_a_model_error_is_printed_and_the_next_line_is_still_processed(error: Exception) -> None:
    agent = FakeAgent([error, reply("back again")])

    out = session(agent, ["first", "second", "/exit"])

    assert any("ollama serve" in line for line in out)
    assert any("back again" in line for line in out)
    # the failed turn leaves nothing behind: retrying does not duplicate the message
    assert [m.content for m in agent.received[1]] == ["second"]


def test_a_bug_is_not_disguised() -> None:
    with pytest.raises(ZeroDivisionError):
        session(FakeAgent([ZeroDivisionError("boom")]), ["question"])
