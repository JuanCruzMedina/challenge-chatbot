"""MCP Server for documentation actions (the only place where actions run).

Confirmed against the installed `mcp` 2.3.0 (task 1.3, see design.md D-1, D-7b, D-7c):
- Server class: `mcp.server.mcpserver.MCPServer` (`FastMCP` was removed in 2.x).
- Register a tool: `server.add_tool(fn)` or the `@server.tool()` decorator; the input schema
  is generated from the type hints.
- Deliberate errors: raise `mcp.server.mcpserver.exceptions.ToolError(message)`; any other
  exception reaches the model only as "Error executing tool <name>".
- Generated schemas are NOT closed and unknown arguments are accepted, so an adapter closes them.
- In-process test client: `mcp.Client(server)`; `list_tools()`, `call_tool()`, results expose `is_error`.

Adding a tool means adding a module to the tools package that defines
`register(server, workspace)`; nothing in this file changes (design.md D-2).
"""
from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

from mcp.server.mcpserver import MCPServer

from ecosystem_assistant.actions.workspace import Workspace

DEFAULT_TOOLS_PACKAGE = "ecosystem_assistant.actions.tools"
SERVER_NAME = "ecosystem-assistant-actions"


class ToolModuleError(RuntimeError):
    """A module in the tools package could not be loaded; startup must not skip it silently."""


def discover_tool_modules(package_name: str = DEFAULT_TOOLS_PACKAGE) -> list[ModuleType]:
    """Import every public module of the tools package, failing loudly with the module's name."""
    try:
        package = importlib.import_module(package_name)
    except Exception as exc:  # noqa: BLE001 - re-raised with context
        raise ToolModuleError(f"cannot import tools package {package_name!r}: {exc}") from exc

    modules: list[ModuleType] = []
    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda i: i.name):
        if info.name.startswith("_"):
            continue
        qualified = f"{package_name}.{info.name}"
        try:
            module = importlib.import_module(qualified)
        except Exception as exc:  # noqa: BLE001 - re-raised with context
            raise ToolModuleError(f"cannot import tool module {qualified!r}: {exc}") from exc
        if not callable(getattr(module, "register", None)):
            raise ToolModuleError(f"tool module {qualified!r} defines no register(server, workspace)")
        modules.append(module)
    return modules


def _close_schemas(server: MCPServer) -> None:
    """Make every tool schema closed (`additionalProperties: false`) and reject unknown arguments.

    The SDK generates open schemas and accepts unknown arguments (design.md D-7c). This touches
    SDK internals on purpose, in one place, guarded by the `mcp~=2.3` pin and by discovery tests.
    """
    for tool in server._tool_manager.list_tools():
        tool.parameters["additionalProperties"] = False
        arg_model = tool.fn_metadata.arg_model
        arg_model.model_config["extra"] = "forbid"
        arg_model.model_rebuild(force=True)


def build_server(
    workspace: Workspace | None = None,
    tools_package: str = DEFAULT_TOOLS_PACKAGE,
) -> MCPServer:
    ws = workspace or Workspace.from_env()
    server = MCPServer(SERVER_NAME)
    for module in discover_tool_modules(tools_package):
        module.register(server, ws)
    _close_schemas(server)
    return server


def main() -> None:
    build_server().run("stdio")


if __name__ == "__main__":
    main()
