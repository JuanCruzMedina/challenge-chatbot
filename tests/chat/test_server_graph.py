"""Spec: the served graph is the agent's loop, discovers tools on every run and leaves no server behind."""
from __future__ import annotations

import importlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ecosystem_assistant.agent.knowledge import KnowledgeService
from ecosystem_assistant.agent.scripted_chat import ScriptedChat, ai_text, ai_tool
from ecosystem_assistant.chat.server_graph import open_graph
from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from ecosystem_assistant.llm.scripted import ScriptedLLM
from tests.actions.test_extensibility import NEW_TOOL
from tests.agent.conftest import run

ROOT = Path(__file__).resolve().parents[2]
MCP_TOOLS = ["add_document", "update_document", "mark_document_obsolete"]


def server_processes() -> int:
    out = subprocess.run(["pgrep", "-f", "ecosystem_assistant.actions.server"], capture_output=True, text=True)
    return len([line for line in out.stdout.splitlines() if line.strip()])


def knowledge_for(workspace: Path, tmp_path: Path, llm: ScriptedLLM | None = None) -> KnowledgeService:
    return KnowledgeService(workspace, RetrievalIndex(tmp_path / "index", HashingEmbedder()), llm or ScriptedLLM([]),
                            min_score=0.0)


def options(workspace: Path, tmp_path: Path, chat: ScriptedChat, **extra) -> dict:
    return {"chat": chat, "workspace": workspace, "audit_file": tmp_path / "audit.jsonl",
            "knowledge": knowledge_for(workspace, tmp_path, extra.pop("llm", None)), **extra}


def test_the_graph_has_only_the_agents_two_nodes_and_all_the_tools(workspace_dir: Path, tmp_path: Path) -> None:
    chat = ScriptedChat(script=[ai_text("hello")])

    async def scenario():
        async with open_graph(**options(workspace_dir, tmp_path, chat)) as graph:
            nodes = set(graph.get_graph().nodes)
            await graph.ainvoke({"messages": [HumanMessage("hi")]})
            return nodes

    nodes = run(scenario())

    assert nodes == {"__start__", "model", "tools", "__end__"}
    assert sorted(chat.bound_tools[0]) == sorted(["query_knowledge", *MCP_TOOLS])


def test_a_run_returns_the_tool_call_the_tool_result_and_the_reply(workspace_dir: Path, tmp_path: Path) -> None:
    llm = ScriptedLLM([
        {"graph_queries": [{"method": "service_owner", "arguments": {"service": "tracking-service"}}]},
        {"answer": "tracking-team owns it [K1].", "citations": ["K1"]},
    ])
    chat = ScriptedChat(script=[ai_tool("query_knowledge", {"question": "who owns tracking?"}),
                                ai_text("tracking-team owns it.")])

    async def scenario():
        async with open_graph(**options(workspace_dir, tmp_path, chat, llm=llm)) as graph:
            return (await graph.ainvoke({"messages": [HumanMessage("who owns tracking?")]}))["messages"]

    messages = run(scenario())

    assert [type(m) for m in messages] == [HumanMessage, AIMessage, ToolMessage, AIMessage]
    assert messages[1].tool_calls[0]["name"] == "query_knowledge"
    assert "tracking-team" in messages[2].content and messages[3].content == "tracking-team owns it."


def test_a_tool_added_to_the_server_appears_in_the_next_build_only(workspace_dir: Path, tmp_path: Path) -> None:
    package = tmp_path / "plugins" / "served_tools_pkg"
    shutil.copytree(ROOT / "src" / "ecosystem_assistant" / "actions" / "tools", package,
                    ignore=shutil.ignore_patterns("__pycache__"))
    env = {"PYTHONPATH": str(tmp_path / "plugins")}

    async def build() -> list[str]:
        chat = ScriptedChat(script=[ai_text("ok")])
        async with open_graph(**options(workspace_dir, tmp_path, chat), tools_package="served_tools_pkg",
                              extra_env=env) as graph:
            await graph.ainvoke({"messages": [HumanMessage("hi")]})
        return chat.bound_tools[0]

    first = run(build())
    (package / "workspace_services.py").write_text(NEW_TOOL, encoding="utf-8")
    second = run(build())

    assert "list_workspace_services" not in first
    assert "list_workspace_services" in second


def test_no_server_process_remains_after_the_run(workspace_dir: Path, tmp_path: Path) -> None:
    before = server_processes()
    chat = ScriptedChat(script=[ai_text("ok")])

    async def scenario() -> int:
        async with open_graph(**options(workspace_dir, tmp_path, chat)) as graph:
            await graph.ainvoke({"messages": [HumanMessage("hi")]})
            return server_processes()

    assert run(scenario()) == before + 1
    assert server_processes() == before


def test_langgraph_json_points_at_a_graph_that_can_be_imported() -> None:
    config = json.loads((ROOT / "langgraph.json").read_text(encoding="utf-8"))

    assert list(config["graphs"]) == ["agent"]
    module_path, _, attribute = config["graphs"]["agent"].partition(":")
    module = importlib.import_module(module_path.removeprefix("./src/").removesuffix(".py").replace("/", "."))
    assert callable(getattr(module, attribute))
    assert (ROOT / module_path).is_file()


def test_the_factory_makes_no_blocking_call_on_the_event_loop(
    workspace_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`langgraph dev` runs the factory on its event loop and rejects blocking calls (found with the real server).

    This uses the same detector and the factory's real path: the knowledge service built from the environment.
    """
    from blockbuster import BlockBuster

    monkeypatch.chdir(tmp_path)  # the project's index folder is created relative to the working directory
    monkeypatch.setenv("AGENT_DATA_ROOT", str(workspace_dir))
    monkeypatch.setenv("ACTIONS_AUDIT_FILE", str(tmp_path / "audit.jsonl"))
    chat = ScriptedChat(script=[ai_text("ok")])

    async def scenario() -> None:
        async with open_graph(chat=chat) as graph:
            await graph.ainvoke({"messages": [HumanMessage("hi")]})

    blockbuster = BlockBuster()
    blockbuster.activate()
    try:
        run(scenario())
    finally:
        blockbuster.deactivate()
