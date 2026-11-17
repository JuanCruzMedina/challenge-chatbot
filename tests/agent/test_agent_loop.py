"""Spec: the model alone chooses the route; failures go back to it; the loop is capped."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END

from ecosystem_assistant.agent.graph import LIMIT_MESSAGE, MAX_TOOL_CALLS, build_agent_graph, route
from ecosystem_assistant.agent.knowledge import KnowledgeService, make_knowledge_tool
from ecosystem_assistant.agent.mcp_tools import McpToolbox
from ecosystem_assistant.agent.prompts import SYSTEM_PROMPT
from ecosystem_assistant.knowledge.flow.catalog import PLAN_SCHEMA
from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from ecosystem_assistant.llm.scripted import Call, ScriptedLLM
from tests.agent.conftest import run
from tests.agent.fake_chat import ScriptedChat, ai_text, ai_tool, ai_tools

ADD_ARGS = {"service": "notifications-service", "doc_path": "docs/agent-test.md", "content": "# Agent test\n\ntext\n"}
GHOST_ARGS = {"service": "ghost-service", "doc_path": "docs/x.md", "content": "x"}
QUESTION_ARGS = {"question": "Who owns the tracking service?"}


def flow_llm() -> ScriptedLLM:
    """The model the knowledge flow uses: plans nothing, answers by citing whatever evidence it was given."""
    def respond(call: Call) -> Any:
        if call.schema == PLAN_SCHEMA:
            return {"graph_queries": []}
        cited = list(dict.fromkeys(re.findall(r"\[((?:K|D)\d+)\]", call.user.split("EVIDENCE", 1)[1])))
        return {"answer": "the flow answered " + " ".join(f"[{c}]" for c in cited), "citations": cited}
    return ScriptedLLM(responder=respond)


def turn(workspace_dir: Path, audit_file: Path, tmp_path: Path, chat: ScriptedChat, message: str = "hello",
         ) -> tuple[list[Any], ScriptedLLM]:
    """Run one turn against the real MCP server and the real knowledge tool; return the messages and the flow's model."""
    llm = flow_llm()
    knowledge = make_knowledge_tool(
        KnowledgeService(workspace_dir, RetrievalIndex(tmp_path / "index", HashingEmbedder()), llm, min_score=0.0))

    async def scenario():
        async with McpToolbox.stdio(workspace=workspace_dir, audit_file=audit_file) as box:
            graph = build_agent_graph(chat, [knowledge, *box.tools], SYSTEM_PROMPT)
            return (await graph.ainvoke({"messages": [HumanMessage(message)]}))["messages"]

    return run(scenario()), llm


def tool_names_called(messages: list[Any]) -> list[str]:
    return [call["name"] for m in messages if isinstance(m, AIMessage) for call in m.tool_calls]


def test_a_question_is_answered_through_the_knowledge_tool_only(workspace_dir, audit_file, tmp_path) -> None:
    chat = ScriptedChat(script=[ai_tool("query_knowledge", QUESTION_ARGS), ai_text("It is tracking-team.")])

    messages, llm = turn(workspace_dir, audit_file, tmp_path, chat, "Who owns the tracking service?")

    assert tool_names_called(messages) == ["query_knowledge"]
    assert messages[-1].content == "It is tracking-team."
    assert any(c.schema == PLAN_SCHEMA for c in llm.calls)       # the flow ran
    assert not audit_file.exists()                                # no MCP tool wrote anything


def test_an_action_request_runs_the_mcp_tool_the_model_asked_for(workspace_dir, audit_file, tmp_path) -> None:
    chat = ScriptedChat(script=[ai_tool("add_document", ADD_ARGS), ai_text("Created it.")])

    messages, llm = turn(workspace_dir, audit_file, tmp_path, chat, "Create a document")

    assert tool_names_called(messages) == ["add_document"]
    assert (workspace_dir / "repos" / "notifications-service" / "docs" / "agent-test.md").is_file()
    assert llm.calls == []                                        # the knowledge flow did not run


def test_a_request_that_needs_both_runs_them_in_the_order_the_model_chose(workspace_dir, audit_file, tmp_path) -> None:
    chat = ScriptedChat(script=[ai_tool("query_knowledge", QUESTION_ARGS), ai_tool("add_document", ADD_ARGS),
                                ai_text("Looked it up and wrote the document.")])

    messages, _ = turn(workspace_dir, audit_file, tmp_path, chat)

    assert tool_names_called(messages) == ["query_knowledge", "add_document"]


def test_a_turn_that_needs_no_tool_calls_no_tool(workspace_dir, audit_file, tmp_path) -> None:
    messages, llm = turn(workspace_dir, audit_file, tmp_path, ScriptedChat(script=[ai_text("Hello! How can I help?")]))
    assert tool_names_called(messages) == [] and messages[-1].content == "Hello! How can I help?"
    assert llm.calls == [] and not audit_file.exists()


@pytest.mark.parametrize("words", ["Please CREATE a new runbook now", "Who owns the tracking service?",
                                   "delete everything and add a document", "hola, ¿qué tal?"])
def test_the_route_does_not_depend_on_the_words_of_the_message(workspace_dir, audit_file, tmp_path, words) -> None:
    chat = ScriptedChat(script=[ai_tool("query_knowledge", QUESTION_ARGS), ai_text("done")])
    messages, _ = turn(workspace_dir, audit_file, tmp_path, chat, words)
    assert tool_names_called(messages) == ["query_knowledge"]    # the model's choice, whatever the message says


def test_the_only_branch_is_whether_the_models_last_message_asks_for_tools() -> None:
    asks = {"messages": [HumanMessage("anything at all"), ai_tool("a_tool", {})]}
    asks_other_words = {"messages": [HumanMessage("completely different words"), ai_tool("a_tool", {})]}
    replies = {"messages": [HumanMessage("create a document please"), ai_text("no")]}
    replies_other_words = {"messages": [HumanMessage("what is the capital of France"), ai_text("no")]}

    assert route(asks) == route(asks_other_words) == "tools"
    assert route(replies) == route(replies_other_words) == END


def test_the_graph_has_only_a_model_step_and_a_tools_step() -> None:
    chat = ScriptedChat(script=[])
    graph = build_agent_graph(chat, [], SYSTEM_PROMPT)
    assert set(graph.get_graph().nodes) == {"__start__", "model", "tools", "__end__"}


def test_an_mcp_error_is_shown_to_the_model_which_can_then_explain(workspace_dir, audit_file, tmp_path) -> None:
    chat = ScriptedChat(script=[ai_tool("add_document", GHOST_ARGS), ai_text("That service does not exist.")])

    messages, _ = turn(workspace_dir, audit_file, tmp_path, chat)

    shown = next(m for m in chat.seen[1] if isinstance(m, ToolMessage))
    assert shown.status == "error" and "ghost-service" in shown.content and "Valid services" in shown.content
    assert messages[-1].content == "That service does not exist."


def test_a_conflict_outcome_reaches_the_model_unchanged_as_a_result(workspace_dir, audit_file, tmp_path) -> None:
    args = {"service": "payments-service", "doc_path": "docs/api-v1.md", "old_text": "not in the file", "new_text": "x"}
    chat = ScriptedChat(script=[ai_tool("update_document", args), ai_text("It changed meanwhile.")])

    turn(workspace_dir, audit_file, tmp_path, chat)

    shown = next(m for m in chat.seen[1] if isinstance(m, ToolMessage))
    assert shown.status == "success" and json.loads(shown.content)["outcome"] == "conflict"


def test_a_tool_that_does_not_exist_is_reported_with_the_available_names(workspace_dir, audit_file, tmp_path) -> None:
    chat = ScriptedChat(script=[ai_tool("delete_company", {}), ai_text("I cannot do that.")])

    messages, _ = turn(workspace_dir, audit_file, tmp_path, chat)

    shown = next(m for m in chat.seen[1] if isinstance(m, ToolMessage))
    assert shown.status == "error" and "delete_company" in shown.content
    assert all(name in shown.content for name in ("query_knowledge", "add_document", "update_document"))
    assert not audit_file.exists()                                 # nothing ran


def test_a_turn_is_capped_at_six_tool_calls(workspace_dir, audit_file, tmp_path) -> None:
    chat = ScriptedChat(script=[ai_tool("add_document", GHOST_ARGS, f"c{i}") for i in range(10)])

    messages, _ = turn(workspace_dir, audit_file, tmp_path, chat)

    assert MAX_TOOL_CALLS == 6
    assert sum(isinstance(m, ToolMessage) for m in messages) == 6
    assert messages[-1].content == LIMIT_MESSAGE and "six" in LIMIT_MESSAGE
    assert len(chat.seen) == 7                                      # the 7th request was refused, not executed


def test_a_batch_that_would_pass_the_cap_is_refused_as_a_whole(workspace_dir, audit_file, tmp_path) -> None:
    five = [ai_tool("add_document", GHOST_ARGS, f"c{i}") for i in range(5)]
    chat = ScriptedChat(script=[*five, ai_tools(("add_document", GHOST_ARGS), ("add_document", GHOST_ARGS))])

    messages, _ = turn(workspace_dir, audit_file, tmp_path, chat)

    assert sum(isinstance(m, ToolMessage) for m in messages) == 5
    assert messages[-1].content == LIMIT_MESSAGE


def test_the_models_receive_the_system_prompt_first_and_all_the_tools(workspace_dir, audit_file, tmp_path) -> None:
    chat = ScriptedChat(script=[ai_text("hi")])
    turn(workspace_dir, audit_file, tmp_path, chat)

    assert chat.seen[0][0].content == SYSTEM_PROMPT
    assert sorted(chat.bound_tools[0]) == ["add_document", "append_to_document", "mark_document_obsolete", "query_knowledge", "update_document"]
