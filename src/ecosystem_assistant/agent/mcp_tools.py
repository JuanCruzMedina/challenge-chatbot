"""The bridge from an MCP server to LangChain tools (design.md D-3).

APIs confirmed with a throwaway probe against the installed versions (task 1.2):
- ``mcp.Client(StdioServerParameters(command=sys.executable, args=["-m", "<server module>"], env={...}))`` is an
  async context manager; inside one ``async with`` the session stays open for ``list_tools()`` and many
  ``call_tool(name, arguments)`` calls.
- ``(await client.list_tools()).tools`` holds objects with ``name``, ``description`` and ``input_schema`` (a JSON
  Schema dictionary). A call result has ``is_error`` and ``content[0].text``.
- ``langchain_core.tools.StructuredTool(name=..., description=..., args_schema=<JSON Schema dict>,
  coroutine=..., handle_tool_error=True)``: raising ``ToolException(message)`` inside the coroutine becomes a
  tool message with that text and ``status="error"``.
- The server process writes its INFO logs to stderr; they are silenced for the agent (see ``ACTIONS_LOG_LEVEL``).

Nothing here names a tool: the tools are whatever the server lists when it is asked.
"""
from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool, ToolException
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.mcpserver import MCPServer

SERVER_MODULE = "ecosystem_assistant.actions.server"


class McpServerStartError(RuntimeError):
    """The MCP server process did not start. The message carries the server's own error output."""


class McpToolbox:
    """An open session with an MCP server and the LangChain tools built from what the server lists."""

    def __init__(self, target: MCPServer | StdioServerParameters | str) -> None:
        if not isinstance(target, (MCPServer, StdioServerParameters, str)):
            raise TypeError(
                f"An MCP target is a server instance, stdio parameters or a URL, not {type(target).__name__}"
            )
        self._target = target
        self._client: Client | None = None
        self._errlog: Any = None
        self._tools: list[StructuredTool] = []

    @classmethod
    def stdio(
        cls,
        workspace: Path,
        audit_file: Path | None = None,
        tools_package: str | None = None,
        extra_env: Mapping[str, str] | None = None,
    ) -> "McpToolbox":
        """The real actions server started as a subprocess over stdio, writing to ``workspace``."""
        env = {
            "PATH": os.environ.get("PATH", ""),
            "DOCS_WORKSPACE": str(workspace),
            "ACTIONS_LOG_LEVEL": os.environ.get("ACTIONS_LOG_LEVEL", "WARNING"),
        }
        if os.environ.get("PYTHONPATH"):
            env["PYTHONPATH"] = os.environ["PYTHONPATH"]
        if audit_file is not None:
            env["ACTIONS_AUDIT_FILE"] = str(audit_file)
        if tools_package:
            env["ACTIONS_TOOLS_PACKAGE"] = tools_package
        env.update(extra_env or {})
        return cls(StdioServerParameters(command=sys.executable, args=["-m", SERVER_MODULE], env=env))

    # --- session ------------------------------------------------------------------------------------

    async def __aenter__(self) -> "McpToolbox":
        target: Any = self._target
        if isinstance(target, StdioServerParameters):
            # The subprocess writes its errors to a file of our own: the default is sys.stderr, which hosts such as
            # notebooks or test runners replace with an object that has no file number. The file also lets us say
            # why the server did not start.
            self._errlog = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
            target = stdio_client(target, errlog=self._errlog)
        self._client = Client(target)
        try:
            await self._client.__aenter__()
            await self.refresh()
        except BaseException as exc:
            reason = self._server_errors()  # read it before the file is closed
            await self._abandon()
            if isinstance(exc, Exception) and reason:
                raise McpServerStartError(f"The MCP server did not start. Its error output:\n{reason}") from exc
            raise
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        # The client is closed as if the block had succeeded. Handing it the block's exception would make its task
        # group wrap it in an ExceptionGroup, and callers would no longer see the error they expect; returning None
        # here lets the original exception continue on its way untouched.
        await self._abandon()

    async def _abandon(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            try:
                await client.__aexit__(None, None, None)
            except BaseException:  # noqa: BLE001 - a half-open session may fail to close; the cause is reported elsewhere
                pass
        self._close_errlog()

    def _server_errors(self) -> str:
        if self._errlog is None or self._errlog.closed:
            return ""
        self._errlog.flush()
        self._errlog.seek(0)
        return self._errlog.read()[-2000:].strip()

    def _close_errlog(self) -> None:
        if self._errlog is not None and not self._errlog.closed:
            self._errlog.close()
        self._errlog = None

    # --- discovery ----------------------------------------------------------------------------------

    @property
    def tools(self) -> list[StructuredTool]:
        """The tools of the last listing. Call :meth:`refresh` to list again."""
        return list(self._tools)

    async def refresh(self) -> list[StructuredTool]:
        """List the server's tools again; added tools appear and removed tools are gone."""
        assert self._client is not None, "open the toolbox with `async with` first"
        listing = await self._client.list_tools()
        self._tools = [self._build(spec) for spec in listing.tools]
        return self.tools

    def _build(self, spec: Any) -> StructuredTool:
        name = spec.name

        async def call(**arguments: Any) -> str:
            assert self._client is not None
            result = await self._client.call_tool(name, arguments)
            text = "\n".join(c.text for c in result.content if getattr(c, "text", None))
            if result.is_error:
                raise ToolException(text or f"The tool {name} failed without a message.")
            return text

        return StructuredTool(
            name=name,
            description=spec.description or "",
            args_schema=spec.input_schema,  # the server's JSON Schema, as it declares it
            coroutine=call,
            handle_tool_error=True,
        )
