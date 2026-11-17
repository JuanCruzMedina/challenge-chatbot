"""Spec: a conversation turn returns the reply and the record of tool calls as plain data; tools refresh each turn."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from mcp.server.mcpserver import MCPServer

from ecosystem_assistant.agent.agent import Agent
from ecosystem_assistant.agent.knowledge import KnowledgeService, make_knowledge_tool
from ecosystem_assistant.agent.mcp_tools import McpToolbox
from ecosystem_assistant.agent.records import AgentReply
from ecosystem_assistant.knowledge.flow.catalog import PLAN_SCHEMA
from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from ecosystem_assistant.llm.scripted import Call, ScriptedLLM
from tests.agent.conftest import run
from tests.agent.fake_chat import ScriptedChat, ai_text, ai_tool

ADD_ARGS = {"service": "notifications-service", "doc_path": "docs/agent-turn.md", "content": "# Turn\n\ntext\n"}
GHOST_ARGS = {"service": "ghost-service", "doc_path": "docs/x.md", "content": "x"}


def knowledge_service(workspace_dir: Path, tmp_path: Path) -> KnowledgeService:
    def respond(call: Call) -> Any:
        if call.schema == PLAN_SCHEMA:
            return {"graph_queries": []}
        cited = list(dict.fromkeys(re.findall(r"\[((?:K|D)\d+)\]", call.user.split("EVIDENCE", 1)[1])))
        return {"answer": "answer " + " ".join(f"[{c}]" for c in cited), "citations": cited}
    return KnowledgeService(workspace_dir, RetrievalIndex(tmp_path / "index", HashingEmbedder()),
                            ScriptedLLM(responder=respond), min_score=0.0)


def test_the_agent_lists_the_knowledge_tool_and_the_discovered_tools(workspace_dir, audit_file, tmp_path) -> None:
    async def scenario():
        async with Agent.open(chat=ScriptedChat(), workspace=workspace_dir, audit_file=audit_file,
                              knowledge=knowledge_service(workspace_dir, tmp_path)) as agent:
            return agent.tool_names

    names = run(scenario())

    assert names[0] == "query_knowledge"
    assert sorted(names[1:]) == ["add_document", "append_to_document", "create_documentation_ticket", "mark_document_obsolete", "update_document"]


def test_a_turn_returns_the_reply_and_a_record_of_every_tool_call_as_json(workspace_dir, audit_file, tmp_path) -> None:
    chat = ScriptedChat(script=[ai_tool("query_knowledge", {"question": "Who owns the tracking service?"}),
                                ai_tool("add_document", ADD_ARGS, "call-2"), ai_tool("add_document", GHOST_ARGS, "call-3"),
                                ai_text("All done.")])

    async def scenario() -> AgentReply:
        async with Agent.open(chat=chat, workspace=workspace_dir, audit_file=audit_file,
                              knowledge=knowledge_service(workspace_dir, tmp_path)) as agent:
            return await agent.chat("Look something up, then write a document")

    reply = run(scenario())
    data = reply.to_dict()

    assert reply.text == "All done."
    assert [c.name for c in reply.tool_calls] == ["query_knowledge", "add_document", "add_document"]
    assert [c.error for c in reply.tool_calls] == [False, False, True]
    assert reply.tool_calls[1].arguments == ADD_ARGS and "created" in reply.tool_calls[1].result
    assert "ghost-service" in reply.tool_calls[2].result
    assert json.loads(json.dumps(data)) == data
    assert set(data) == {"text", "tool_calls"} and set(data["tool_calls"][0]) == {"name", "arguments", "result", "error"}


def test_the_tools_are_listed_again_at_the_start_of_every_turn() -> None:
    server = MCPServer("dynamic", log_level="WARNING")

    def first() -> str:
        """The first tool."""
        return "one"

    def second() -> str:
        """The second tool."""
        return "two"

    server.add_tool(first)
    chat = ScriptedChat(script=[ai_text("turn one"), ai_text("turn two")])

    async def scenario():
        async with McpToolbox(server) as box:
            agent = Agent(chat, box, make_knowledge_tool(KnowledgeService(Path("."), None, None)))  # type: ignore[arg-type]
            await agent.chat("hello")
            server.add_tool(second)  # the server changes between two turns; the agent's code does not
            await agent.chat("hello again")

    run(scenario())

    assert sorted(chat.bound_tools[0]) == ["first", "query_knowledge"]
    assert sorted(chat.bound_tools[1]) == ["first", "query_knowledge", "second"]


def test_a_conversation_can_be_passed_as_messages_and_only_the_new_ones_are_returned(workspace_dir, audit_file, tmp_path) -> None:
    chat = ScriptedChat(script=[ai_text("Your name is Ana.")])
    history = [HumanMessage("My name is Ana."), AIMessage("Nice to meet you, Ana."), HumanMessage("What is my name?")]

    async def scenario():
        async with Agent.open(chat=chat, workspace=workspace_dir, audit_file=audit_file,
                              knowledge=knowledge_service(workspace_dir, tmp_path)) as agent:
            return await agent.chat(history)

    reply = run(scenario())

    assert reply.text == "Your name is Ana."
    assert [m.content for m in reply.messages] == ["Your name is Ana."]
    assert [m.content for m in chat.seen[0][1:]] == ["My name is Ana.", "Nice to meet you, Ana.", "What is my name?"]


def test_plain_role_and_content_dictionaries_are_accepted_too(workspace_dir, audit_file, tmp_path) -> None:
    chat = ScriptedChat(script=[ai_text("ok")])

    async def scenario():
        async with Agent.open(chat=chat, workspace=workspace_dir, audit_file=audit_file,
                              knowledge=knowledge_service(workspace_dir, tmp_path)) as agent:
            return await agent.chat([{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"},
                                     {"role": "user", "content": "and now?"}])

    run(scenario())

    assert [type(m).__name__ for m in chat.seen[0]] == ["SystemMessage", "HumanMessage", "AIMessage", "HumanMessage"]


def test_a_reply_made_of_content_blocks_is_joined_into_text(workspace_dir, audit_file, tmp_path) -> None:
    blocks = AIMessage(content=[{"type": "text", "text": "first "}, {"type": "text", "text": "second"}])

    async def scenario():
        async with Agent.open(chat=ScriptedChat(script=[blocks]), workspace=workspace_dir, audit_file=audit_file,
                              knowledge=knowledge_service(workspace_dir, tmp_path)) as agent:
            return await agent.chat("hi")

    assert run(scenario()).text == "first second"


def test_opening_without_a_workspace_says_how_to_create_it(tmp_path: Path) -> None:
    async def scenario():
        async with Agent.open(chat=ScriptedChat(), workspace=tmp_path / "does-not-exist"):
            pass

    with pytest.raises(FileNotFoundError, match="seed_workspace.py"):
        run(scenario())
