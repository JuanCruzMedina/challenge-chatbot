"""Helpers shared by the agent tests."""
from __future__ import annotations

import shutil
from pathlib import Path

from mcp import Client

from ecosystem_assistant.actions.server import build_server
from ecosystem_assistant.actions.workspace import Workspace
from tests.agent.conftest import run
from tests.data.helpers import SAMPLE


def real_mcp_tool_names(scratch: Path) -> list[str]:
    """The names the real server declares today, read from the server itself (so new tools are covered too)."""
    shutil.copytree(SAMPLE, scratch / "ws")
    server = build_server(Workspace(scratch / "ws", scratch / "audit.jsonl"))

    async def listing() -> list[str]:
        async with Client(server) as client:
            return [t.name for t in (await client.list_tools()).tools]

    return run(listing())
