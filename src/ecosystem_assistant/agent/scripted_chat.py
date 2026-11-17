"""A scripted chat model: replays AI messages (with tool calls) and records what it was given.

For tests and for demonstrations that need no model: the agent runs its real loop, real tools and real server, and only
the model's decisions are scripted.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


def ai_tool(name: str, args: dict[str, Any], call_id: str = "call-1") -> AIMessage:
    """A model turn that asks for one tool."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}])


def ai_tools(*calls: tuple[str, dict[str, Any]]) -> AIMessage:
    """A model turn that asks for several tools at once."""
    return AIMessage(content="", tool_calls=[
        {"name": n, "args": a, "id": f"call-{i}", "type": "tool_call"} for i, (n, a) in enumerate(calls, 1)])


def ai_text(text: str) -> AIMessage:
    """A model turn that replies and asks for nothing."""
    return AIMessage(content=text)


class ScriptedChat(BaseChatModel):
    """Answers with the next item of ``script``: an AI message, an exception to raise, or a function of the messages."""

    script: list[Any] = Field(default_factory=list)
    responder: Callable[[list[BaseMessage]], AIMessage] | None = None
    seen: list[list[BaseMessage]] = Field(default_factory=list)       # the messages of every call
    bound_tools: list[list[str]] = Field(default_factory=list)       # the tool names bound at every call

    @property
    def _llm_type(self) -> str:
        return "scripted-chat"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedChat":
        names = [t["function"]["name"] if isinstance(t, dict) else t.name for t in tools]
        self.bound_tools.append(names)
        return self

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: Any = None,
                  **kwargs: Any) -> ChatResult:
        self.seen.append(list(messages))
        if self.responder is not None:
            item: Any = self.responder(messages)
        elif self.script:
            item = self.script.pop(0)
        else:
            raise AssertionError("the scripted chat model ran out of responses")
        if isinstance(item, Exception):
            raise item
        return ChatResult(generations=[ChatGeneration(message=item)])

    async def _agenerate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: Any = None,
                         **kwargs: Any) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)
