"""Spec: the entry point reports a missing workspace, runs a session and leaves no server behind."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ecosystem_assistant.agent.agent import Agent
from ecosystem_assistant.agent.knowledge import KnowledgeService
from ecosystem_assistant.agent.scripted_chat import ScriptedChat, ai_text, ai_tool
from ecosystem_assistant.chat.__main__ import main
from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from ecosystem_assistant.llm.scripted import ScriptedLLM


def server_processes() -> int:
    out = subprocess.run(["pgrep", "-f", "ecosystem_assistant.actions.server"], capture_output=True, text=True)
    return len([line for line in out.stdout.splitlines() if line.strip()])


def test_a_missing_workspace_exits_with_code_2_and_the_seed_command(tmp_path: Path) -> None:
    printed: list[str] = []

    code = main(["--workspace", str(tmp_path / "nowhere")], write=printed.append)

    assert code == 2
    assert any("uv run python scripts/seed_workspace.py" in line for line in printed)


def test_a_session_runs_against_a_seeded_workspace_and_leaves_no_server(workspace_dir: Path, tmp_path: Path) -> None:
    flow_model = ScriptedLLM([
        {"graph_queries": [{"method": "service_owner", "arguments": {"service": "tracking-service"}}]},
        {"answer": "tracking-team owns it [K1].", "citations": ["K1"]},
    ])
    knowledge = KnowledgeService(workspace_dir, RetrievalIndex(tmp_path / "index", HashingEmbedder()), flow_model,
                                 min_score=0.0)
    chat = ScriptedChat(script=[ai_tool("query_knowledge", {"question": "who owns tracking?"}),
                                ai_text("tracking-team owns it.")])

    def factory(workspace: Path | None):
        return Agent.open(chat=chat, workspace=workspace, audit_file=tmp_path / "audit.jsonl", knowledge=knowledge)

    typed = iter(["who owns tracking?", "/exit"])
    printed: list[str] = []
    before = server_processes()

    code = main(["--workspace", str(workspace_dir)], agent_factory=factory,
                read=lambda _p: next(typed), write=printed.append)

    assert code == 0
    text = "\n".join(printed)
    assert "tracking-team owns it." in text and "query_knowledge" in text
    assert server_processes() == before


def test_a_keyboard_interrupt_leaves_cleanly_and_stops_the_server(workspace_dir: Path, tmp_path: Path) -> None:
    knowledge = KnowledgeService(workspace_dir, RetrievalIndex(tmp_path / "index", HashingEmbedder()),
                                 ScriptedLLM([]), min_score=0.0)

    def factory(workspace: Path | None):
        return Agent.open(chat=ScriptedChat(script=[]), workspace=workspace, audit_file=tmp_path / "a.jsonl",
                          knowledge=knowledge)

    def interrupt(_prompt: str) -> str:
        raise KeyboardInterrupt

    before = server_processes()
    code = main(["--workspace", str(workspace_dir)], agent_factory=factory, read=interrupt, write=lambda _l: None)

    assert code == 0
    assert server_processes() == before
