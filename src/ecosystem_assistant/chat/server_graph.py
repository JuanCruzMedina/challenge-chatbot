"""The agent's loop as a graph for ``langgraph dev`` (Agent Chat UI).

Confirmed with a throwaway probe against langgraph-cli 0.4.43 / langgraph-api 0.18.2 (task 1.2):
- ``langgraph.json`` entries ``"name": "./file.py:callable"`` accept a plain function taking ``config``, an async
  function with no arguments, and an ``@asynccontextmanager`` function.
- The callable runs on **every run** (twice invoked, twice called), so tools can be listed again each time.
- An async context manager is opened when the run starts and closed when it ends: what we need to start and stop the
  MCP server subprocess around a run.
- The ``env`` key is accepted in ``langgraph.json``.
- A run is served at ``POST /runs/wait`` with ``assistant_id`` set to the graph's name and a ``messages`` input.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from ecosystem_assistant.agent.agent import Agent
from ecosystem_assistant.agent.graph import build_agent_graph
from ecosystem_assistant.agent.prompts import SYSTEM_PROMPT
from ecosystem_assistant.agent.settings import chat_model_from_env, translate_model_error


@asynccontextmanager
async def open_graph(chat: BaseChatModel | None = None, **agent_options: Any) -> AsyncIterator[Any]:
    """Start the MCP server, list its tools and yield the agent's loop built with them; stop the server afterwards.

    The options are those of ``Agent.open`` (workspace, audit file, knowledge service, tools package, extra
    environment). The graph is the agent's own: same builder, same prompt, same two nodes. Nothing is added.
    """
    model = chat or chat_model_from_env()
    async with Agent.open(chat=model, **agent_options) as agent:
        yield build_agent_graph(model, agent.tools, SYSTEM_PROMPT, translate_error=translate_model_error())


# What ``langgraph.json`` points at: LangGraph calls it on every run, with everything taken from the environment.
agent_graph = open_graph
