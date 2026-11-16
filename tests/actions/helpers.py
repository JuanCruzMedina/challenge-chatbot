"""Small helpers to talk to an in-process MCP server from synchronous tests."""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from mcp import Client
from mcp.server.mcpserver import MCPServer

T = TypeVar("T")


def with_client(server: MCPServer, body: Callable[[Client], Awaitable[T]]) -> T:
    async def run() -> T:
        async with Client(server) as client:
            return await body(client)

    return asyncio.run(run())


def payload(result: Any) -> dict[str, Any]:
    """The JSON object a tool returned, whether it came structured or as text."""
    if getattr(result, "structured_content", None):
        return dict(result.structured_content)
    return json.loads(result.content[0].text)
