"""Spec: the prompt teaches confirmation, conflict checks and what the write tools can edit (no tool is named)."""
from __future__ import annotations

from pathlib import Path

from ecosystem_assistant.actions.server import build_server
from ecosystem_assistant.actions.workspace import Workspace
from ecosystem_assistant.agent.agent import Agent
from ecosystem_assistant.agent.prompts import SYSTEM_PROMPT
from tests.actions.helpers import with_client
from tests.agent.conftest import run
from tests.agent.fake_chat import ScriptedChat, ai_text, ai_tool
from tests.agent.test_agent import knowledge_service


def test_the_prompt_carries_the_three_rules() -> None:
    text = " ".join(SYSTEM_PROMPT.lower().split())
    assert "confirms" in text and "order to act" in text          # a "yes" is the order to act
    assert "contradict" in text and "knowledge tool" in text      # conflicts are checked, then asked
    assert "markdown" in text                                      # write tools edit markdown documents only
    assert len(SYSTEM_PROMPT.splitlines()) < 30


def test_the_prompt_names_no_tool_of_the_server(workspace_dir: Path, audit_file: Path) -> None:
    async def names(client):
        return [t.name for t in (await client.list_tools()).tools]

    tools = with_client(build_server(Workspace(root=workspace_dir, audit_file=audit_file)), names)
    assert tools
    assert not [name for name in tools if name in SYSTEM_PROMPT]


def test_after_a_confirmation_a_scripted_turn_writes_once(workspace_dir: Path, audit_file: Path, tmp_path: Path) -> None:
    args = {"service": "orders-service", "doc_path": "docs/product-owner.md",
            "text": "Leo Messi is the Product Owner of orders-team."}
    chat = ScriptedChat(script=[ai_tool("append_to_document", args), ai_text("Done: docs/product-owner.md written.")])
    history = [
        {"role": "user", "content": "Leo Messi is the Product Owner of orders-team"},
        {"role": "assistant", "content": "I will add it to docs/product-owner.md of orders-service. Confirm?"},
        {"role": "user", "content": "yes"},
    ]

    async def scenario():
        async with Agent.open(chat=chat, workspace=workspace_dir, audit_file=audit_file,
                              knowledge=knowledge_service(workspace_dir, tmp_path)) as agent:
            return await agent.chat(history)

    reply = run(scenario())

    assert [c.name for c in reply.tool_calls] == ["append_to_document"]
    assert not reply.tool_calls[0].error
    written = workspace_dir / "repos" / "orders-service" / "docs" / "product-owner.md"
    assert written.read_text(encoding="utf-8") == "Leo Messi is the Product Owner of orders-team.\n"
    assert "written" in reply.text

