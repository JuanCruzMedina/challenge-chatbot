"""Spec: the reply is rendered and the notes are dimmed (polish-terminal-chat)."""
from __future__ import annotations

import asyncio
import io

from rich.console import Console

from ecosystem_assistant.chat.render import RichPrinter
from ecosystem_assistant.chat.terminal import run_chat
from tests.chat.test_terminal import FakeAgent, reply
from ecosystem_assistant.agent.settings import AgentModelError

TABLE = "| Team | Lead |\n|---|---|\n| orders-team | Tomás Aguirre |\n\nThis is **important** [K1]."


def printer(terminal: bool) -> tuple[RichPrinter, io.StringIO]:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=terminal, color_system="standard" if terminal else None, width=60)
    return RichPrinter(console), buffer


def test_a_markdown_table_is_drawn_and_bold_markers_are_not_shown() -> None:
    p, out = printer(terminal=True)

    p.reply(TABLE)

    text = out.getvalue()
    assert "orders-team" in text and "Tomás Aguirre" in text
    assert "|---|" not in text and "**" not in text
    assert "[K1]" in text, "citation markers stay as the model wrote them"


def test_the_notes_are_dimmed_and_the_errors_are_red() -> None:
    p, out = printer(terminal=True)

    p.note("  ↳ called: query_knowledge")
    p.error("[error] cannot reach the model")

    text = out.getvalue()
    assert "\x1b[2m" in text            # dim
    assert "\x1b[31m" in text           # red
    assert "called: query_knowledge" in text and "cannot reach the model" in text


def test_a_square_bracket_in_a_note_is_not_taken_as_markup() -> None:
    p, out = printer(terminal=True)

    p.error("[error] Cannot reach [bold]x[/bold]")

    assert "[bold]x[/bold]" in out.getvalue()


def test_a_pipe_gets_no_escape_sequences() -> None:
    p, out = printer(terminal=False)

    p.reply(TABLE)
    p.note("  ↳ called: query_knowledge")
    p.error("[error] boom")

    assert "\x1b" not in out.getvalue()
    assert "Tomás Aguirre" in out.getvalue() and "called: query_knowledge" in out.getvalue()


def test_the_loop_sends_each_kind_of_output_to_its_own_function() -> None:
    agent = FakeAgent([reply("tracking-team owns it", "query_knowledge"), AgentModelError("model down")])
    lines = iter(["who owns tracking?", "again", "/exit"])
    replies: list[str] = []
    notes: list[str] = []
    errors: list[str] = []
    plain: list[str] = []

    asyncio.run(run_chat(agent, lambda _p: next(lines), plain.append,
                         write_reply=replies.append, write_note=notes.append, write_error=errors.append))

    assert replies == ["tracking-team owns it"]
    assert any("query_knowledge" in n for n in notes)
    assert errors == ["[error] model down"]
    assert not any("tracking-team" in line for line in plain), "the reply is not also printed plainly"
