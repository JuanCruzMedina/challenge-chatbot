"""The agent: a chat model, the knowledge tool and the tools of an MCP server (design.md D-1 to D-8).

The agent never decides what a request is. It gives the model the conversation and the tools, runs what the model asks
for, and returns the reply with a record of the tool calls. Tools are listed again at the start of every turn.
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from ecosystem_assistant.agent.graph import MAX_TOOL_CALLS, build_agent_graph
from ecosystem_assistant.agent.knowledge import DEFAULT_DATA_ROOT, KnowledgeService, make_knowledge_tool
from ecosystem_assistant.agent.mcp_tools import McpToolbox
from ecosystem_assistant.agent.prompts import SYSTEM_PROMPT
from ecosystem_assistant.agent.records import AgentReply, message_text, records_from_messages
from ecosystem_assistant.agent.settings import chat_model_from_env, translate_model_error

Message = BaseMessage | Mapping[str, Any]


class Agent:
    def __init__(
        self,
        model: BaseChatModel,
        toolbox: McpToolbox,
        knowledge_tool: BaseTool,
        system_prompt: str = SYSTEM_PROMPT,
        max_tool_calls: int = MAX_TOOL_CALLS,
        translate_error: Callable[[Exception], Exception] | None = None,
    ) -> None:
        self._model = model
        self._toolbox = toolbox
        self._knowledge_tool = knowledge_tool
        self._system_prompt = system_prompt
        self._max_tool_calls = max_tool_calls
        self._translate_error = translate_error

    # --- opening ------------------------------------------------------------------------------------

    @classmethod
    @asynccontextmanager
    async def open(
        cls,
        chat: BaseChatModel | None = None,
        workspace: Path | None = None,
        audit_file: Path | None = None,
        knowledge: KnowledgeService | None = None,
        tools_package: str | None = None,
        extra_env: Mapping[str, str] | None = None,
    ) -> AsyncIterator["Agent"]:
        """Start the MCP server, discover its tools and yield an agent; the server stops when the block ends.

        By default everything comes from the environment: the Ollama model, the workspace of ``AGENT_DATA_ROOT``
        (default ``var/workspace``, which both the actions and the knowledge side use) and the project's index.
        """
        # File-system work runs in a thread: hosts such as `langgraph dev` reject blocking calls on the event loop.
        root, service = await asyncio.to_thread(_prepare, workspace, knowledge)
        toolbox = McpToolbox.stdio(workspace=root, audit_file=audit_file, tools_package=tools_package,
                                   extra_env=extra_env)
        async with toolbox:
            yield cls(chat or chat_model_from_env(), toolbox, make_knowledge_tool(service),
                      translate_error=translate_model_error())

    # --- tools --------------------------------------------------------------------------------------

    @property
    def tools(self) -> list[BaseTool]:
        return [self._knowledge_tool, *self._toolbox.tools]

    @property
    def tool_names(self) -> list[str]:
        return [tool.name for tool in self.tools]

    # --- a turn -------------------------------------------------------------------------------------

    async def chat(self, messages: str | Sequence[Message]) -> AgentReply:
        """Run one turn over the conversation so far (or a single message) and return the reply."""
        await self._toolbox.refresh()  # the tool set always follows the server
        graph = build_agent_graph(self._model, self.tools, self._system_prompt, self._max_tool_calls,
                                  self._translate_error)
        history = _as_messages(messages)
        result = await graph.ainvoke({"messages": history})
        new = list(result["messages"][len(history):])
        last_reply = next((m for m in reversed(new) if isinstance(m, AIMessage)), None)
        return AgentReply(
            text=message_text(last_reply) if last_reply is not None else "",
            tool_calls=records_from_messages(new),
            messages=new,
        )


def _prepare(workspace: Path | None, knowledge: KnowledgeService | None) -> tuple[Path, KnowledgeService]:
    """The workspace folder (checked) and the knowledge service; both touch the disk."""
    root = Path(workspace or os.environ.get("AGENT_DATA_ROOT") or DEFAULT_DATA_ROOT)
    if not (root / "company.yaml").is_file():
        raise FileNotFoundError(
            f"There is no ecosystem data in {root}. Create the workspace with: "
            f"uv run python scripts/seed_workspace.py"
        )
    return root, knowledge or KnowledgeService.from_env()


def _as_messages(messages: str | Sequence[Message]) -> list[BaseMessage]:
    if isinstance(messages, str):
        return [HumanMessage(messages)]
    converted: list[BaseMessage] = []
    for message in messages:
        if isinstance(message, BaseMessage):
            converted.append(message)
            continue
        role, content = message.get("role"), message.get("content", "")
        if role in ("user", "human"):
            converted.append(HumanMessage(content))
        elif role in ("assistant", "ai"):
            converted.append(AIMessage(content))
        elif role == "system":
            converted.append(SystemMessage(content))
        else:
            raise ValueError(f"Unknown message role {role!r}; use user, assistant or system.")
    return converted
