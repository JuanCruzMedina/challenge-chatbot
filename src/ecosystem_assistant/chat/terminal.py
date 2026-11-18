"""The terminal conversation loop (design.md D-1).

It is passive: it sends the conversation to the agent and prints what comes back. The only thing it ever looks at in
a typed line is whether it is the exit command or empty; it does not know what a question or an action is.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from langchain_core.messages import BaseMessage, HumanMessage

from ecosystem_assistant.agent.records import AgentReply
from ecosystem_assistant.agent.settings import AgentModelError
from ecosystem_assistant.llm.port import LLMUnavailableError

EXIT_COMMAND = "/exit"
PROMPT = "you> "


class ChatAgent(Protocol):
    async def chat(self, messages: list[BaseMessage]) -> AgentReply: ...


async def run_chat(
    agent: ChatAgent,
    read: Callable[[str], str] = input,
    write: Callable[[str], Any] = print,
    write_reply: Callable[[str], Any] | None = None,
    write_note: Callable[[str], Any] | None = None,
    write_error: Callable[[str], Any] | None = None,
) -> None:
    """Talk to the agent until ``/exit`` or the end of the input. The conversation is kept between turns.

    ``write`` prints plain lines. The optional outputs let a caller show replies, notes (the greeting and the line of
    called tools) and errors in their own way; each one falls back to ``write``, so a plain caller sees plain text.
    """
    show_reply = write_reply or (lambda text: write(f"assistant> {text}"))
    show_note = write_note or write
    show_error = write_error or write
    history: list[BaseMessage] = []
    show_note(f"Type your message, or {EXIT_COMMAND} to leave.")
    while True:
        try:
            line = read(PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            write("")
            return
        if line == EXIT_COMMAND:
            return
        if not line:
            continue
        pending = [*history, HumanMessage(line)]
        try:
            reply = await agent.chat(pending)
        except (AgentModelError, LLMUnavailableError) as error:
            show_error(f"[error] {error}")  # the turn is dropped from the history, so a retry does not duplicate it
            continue
        history = [*pending, *reply.messages]
        show_reply(reply.text)
        if reply.tool_calls:
            names = ", ".join(dict.fromkeys(call.name for call in reply.tool_calls))
            show_note(f"  ↳ called: {names}")
