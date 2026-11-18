"""Spec: MCP tools are discovered at runtime and keep the name, description and schema the server declares."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from langchain_core.tools import ToolException
from mcp import Client
from mcp.server.mcpserver import MCPServer

from ecosystem_assistant.actions import tools as default_tools
from ecosystem_assistant.actions.server import build_server
from ecosystem_assistant.actions.workspace import Workspace
from ecosystem_assistant.agent.mcp_tools import McpServerStartError, McpToolbox
from tests.actions.test_extensibility import NEW_TOOL
from tests.agent.conftest import run

DEFAULT_NAMES = ["add_document", "append_to_document", "mark_document_obsolete", "update_document"]


def server_processes() -> int:
    out = subprocess.run(["pgrep", "-f", "ecosystem_assistant.actions.server"], capture_output=True, text=True)
    return len([line for line in out.stdout.splitlines() if line.strip()])


def declared_by_the_server(workspace_dir: Path, audit_file: Path) -> dict[str, Any]:
    # The server process asks for confirmation by default, so the reference server does too.
    server = build_server(Workspace(workspace_dir, audit_file, confirm_edits=True))

    async def listing():
        async with Client(server) as client:
            return {t.name: t for t in (await client.list_tools()).tools}

    return run(listing())


def test_the_tools_of_the_real_server_are_discovered_over_stdio(workspace_dir: Path, audit_file: Path) -> None:
    declared = declared_by_the_server(workspace_dir, audit_file)

    async def scenario():
        async with McpToolbox.stdio(workspace=workspace_dir, audit_file=audit_file) as box:
            return {t.name: t for t in box.tools}

    found = run(scenario())

    assert sorted(found) == DEFAULT_NAMES
    for name, tool in found.items():
        assert tool.description == declared[name].description
        assert tool.args_schema == declared[name].input_schema  # the JSON Schema, untouched
        assert tool.args_schema["additionalProperties"] is False and tool.args_schema["required"]


def test_an_in_process_server_can_be_the_target_too(workspace_dir: Path, audit_file: Path) -> None:
    server = build_server(Workspace(workspace_dir, audit_file))

    async def scenario():
        async with McpToolbox(server) as box:
            return sorted(t.name for t in box.tools)

    assert run(scenario()) == DEFAULT_NAMES


def test_closing_the_toolbox_leaves_no_server_process_behind(workspace_dir: Path, audit_file: Path) -> None:
    before = server_processes()

    async def scenario() -> int:
        async with McpToolbox.stdio(workspace=workspace_dir, audit_file=audit_file):
            return server_processes()

    during = run(scenario())

    assert during == before + 1
    assert server_processes() == before


# --- calling the tools -----------------------------------------------------------------------------------

def call(workspace_dir: Path, audit_file: Path, name: str, arguments: dict[str, Any]) -> tuple[Any, Any]:
    """Return (the text the tool gives the model, the exception its coroutine raises, if any)."""
    async def scenario():
        async with McpToolbox.stdio(workspace=workspace_dir, audit_file=audit_file) as box:
            tool = next(t for t in box.tools if t.name == name)
            text = await tool.ainvoke(arguments)
            try:
                await tool.coroutine(**arguments)
                raised = None
            except ToolException as exc:
                raised = exc
            return text, raised

    return run(scenario())


def test_a_successful_call_returns_the_servers_text(workspace_dir: Path, audit_file: Path) -> None:
    args = {"service": "notifications-service", "doc_path": "docs/bridge-test.md", "content": "# Bridge\n\ntext\n"}
    async def scenario():
        async with McpToolbox.stdio(workspace=workspace_dir, audit_file=audit_file) as box:
            tool = next(t for t in box.tools if t.name == "add_document")
            return await tool.ainvoke(args)

    text = run(scenario())

    assert json.loads(text)["outcome"] == "created"
    assert (workspace_dir / "repos" / "notifications-service" / "docs" / "bridge-test.md").is_file()


def test_an_error_result_becomes_a_tool_error_with_the_servers_message(workspace_dir: Path, audit_file: Path) -> None:
    args = {"service": "ghost-service", "doc_path": "docs/x.md", "content": "x"}

    text, raised = call(workspace_dir, audit_file, "add_document", args)

    assert isinstance(raised, ToolException)
    assert "ghost-service" in str(raised) and "Valid services" in str(raised)
    assert "ghost-service" in text  # what the model is shown when the tool is called through LangChain


def test_a_conflict_outcome_is_a_normal_result_not_an_error(workspace_dir: Path, audit_file: Path) -> None:
    args = {"service": "payments-service", "doc_path": "docs/api-v1.md", "old_text": "text that is not there",
            "new_text": "x"}

    text, raised = call(workspace_dir, audit_file, "update_document", args)

    assert raised is None
    assert json.loads(text)["outcome"] == "conflict"


def test_invalid_arguments_become_a_tool_error(workspace_dir: Path, audit_file: Path) -> None:
    args = {"service": "payments-service", "doc_path": "docs/x.md", "content": "c", "surprise": 1}
    _text, raised = call(workspace_dir, audit_file, "add_document", args)
    assert isinstance(raised, ToolException)


# --- discovery and refresh -----------------------------------------------------------------------------

def test_a_refresh_sees_tools_added_and_removed_at_runtime() -> None:
    server = MCPServer("dynamic", log_level="WARNING")

    def first() -> str:
        """The first tool."""
        return "one"

    def second(thing: str) -> str:
        """The second tool."""
        return f"two {thing}"

    server.add_tool(first)

    async def scenario():
        async with McpToolbox(server) as box:
            seen = [sorted(t.name for t in box.tools)]
            server.add_tool(second)
            seen.append(sorted(t.name for t in box.tools))  # not refreshed yet: same tools as before
            await box.refresh()
            seen.append(sorted(t.name for t in box.tools))
            server.remove_tool("first")
            await box.refresh()
            seen.append(sorted(t.name for t in box.tools))
            tool = next(t for t in box.tools if t.name == "second")
            return seen, await tool.ainvoke({"thing": "x"})

    seen, result = run(scenario())

    assert seen == [["first"], ["first"], ["first", "second"], ["second"]]
    assert result == "two x"


def test_a_tool_added_to_the_servers_package_is_available_with_its_own_schema(
    workspace_dir: Path, audit_file: Path, tmp_path: Path
) -> None:
    package = tmp_path / "plugins" / "bridge_tools_pkg"
    shutil.copytree(Path(default_tools.__file__).parent, package, ignore=shutil.ignore_patterns("__pycache__"))
    (package / "workspace_services.py").write_text(NEW_TOOL, encoding="utf-8")

    async def scenario():
        box = McpToolbox.stdio(workspace=workspace_dir, audit_file=audit_file, tools_package="bridge_tools_pkg",
                               extra_env={"PYTHONPATH": str(tmp_path / "plugins")})
        async with box:
            tool = next(t for t in box.tools if t.name == "list_workspace_services")
            return sorted(t.name for t in box.tools), tool.args_schema, await tool.ainvoke({"prefix": "pay"})

    names, schema, result = run(scenario())

    assert names == sorted([*DEFAULT_NAMES, "list_workspace_services"])
    assert schema["additionalProperties"] is False and "prefix" in schema["properties"]
    assert json.loads(result) == {"services": ["payments-service"]}


def test_an_exception_inside_the_block_reaches_the_caller_unwrapped_and_the_server_stops(
    workspace_dir: Path, audit_file: Path
) -> None:
    class Boom(Exception):
        pass

    before = server_processes()

    async def scenario() -> None:
        async with McpToolbox.stdio(workspace=workspace_dir, audit_file=audit_file):
            raise Boom("raised by the caller inside the block")

    with pytest.raises(Boom, match="inside the block"):  # not an ExceptionGroup
        run(scenario())
    assert server_processes() == before


def test_a_server_that_does_not_start_reports_why(workspace_dir: Path, audit_file: Path) -> None:
    async def scenario() -> None:
        async with McpToolbox.stdio(workspace=workspace_dir, audit_file=audit_file,
                                    tools_package="no_such_tools_package_zzz"):
            pass

    with pytest.raises(McpServerStartError) as exc:
        run(scenario())

    assert "no_such_tools_package_zzz" in str(exc.value)  # the server's own error, not a bare "connection closed"


def test_the_toolbox_works_when_the_process_has_replaced_stderr(
    workspace_dir: Path, audit_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hosts such as notebooks, test runners or servers replace sys.stderr with an object that has no file number."""
    import io
    import sys

    monkeypatch.setattr(sys, "stderr", io.StringIO())

    async def scenario():
        async with McpToolbox.stdio(workspace=workspace_dir, audit_file=audit_file) as box:
            return sorted(t.name for t in box.tools)

    assert run(scenario()) == DEFAULT_NAMES


def test_a_tool_that_needs_an_unknown_target_fails_to_open_with_a_clear_error() -> None:
    with pytest.raises(TypeError):
        McpToolbox(object())  # type: ignore[arg-type]
