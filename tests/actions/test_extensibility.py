"""Spec: new tools are added without changing existing code."""
from __future__ import annotations

import hashlib
import shutil
import sys
import textwrap
from pathlib import Path

import pytest

from ecosystem_assistant.actions import tools as default_tools
from ecosystem_assistant.actions.server import ToolModuleError, build_server
from ecosystem_assistant.actions.workspace import Workspace
from tests.actions.helpers import payload, with_client

DEFAULT_NAMES = {"add_document", "append_to_document", "update_document", "mark_document_obsolete", "link_document"}
SERVER_PY = Path(__file__).resolve().parents[2] / "src" / "ecosystem_assistant" / "actions" / "server.py"

NEW_TOOL = textwrap.dedent(
    '''
    from typing import Annotated, Any

    from pydantic import Field


    def register(server, workspace) -> None:
        @server.tool(description="List the services of the workspace. Do NOT use it to answer documentation questions.")
        def list_workspace_services(
            prefix: Annotated[str, Field(description="Only services starting with this prefix.")] = "",
        ) -> dict[str, Any]:
            return {"services": [s for s in workspace.list_services() if s.startswith(prefix)]}
    '''
)


def _digest(paths: list[Path]) -> dict[str, str]:
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


@pytest.fixture
def tools_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, Path]:
    """A throwaway copy of the real tools package, importable under a temporary name."""
    name = "throwaway_tools_pkg"
    target = tmp_path / name
    shutil.copytree(Path(default_tools.__file__).parent, target, ignore=shutil.ignore_patterns("__pycache__"))
    monkeypatch.syspath_prepend(str(tmp_path))
    yield name, target
    for loaded in [m for m in sys.modules if m == name or m.startswith(f"{name}.")]:
        del sys.modules[loaded]


def test_a_new_tool_module_appears_and_defaults_are_unchanged(
    workspace: Workspace, tools_copy: tuple[str, Path]
) -> None:
    name, folder = tools_copy
    real_files = sorted(Path(default_tools.__file__).parent.glob("*.py")) + [SERVER_PY]
    before = _digest(real_files)

    (folder / "workspace_services.py").write_text(NEW_TOOL, encoding="utf-8")
    server = build_server(workspace, tools_package=name)

    async def body(client):
        listed = {t.name: t for t in (await client.list_tools()).tools}
        new_result = await client.call_tool("list_workspace_services", {"prefix": "pay"})
        old_result = await client.call_tool(
            "add_document",
            {"service": "payments-service", "doc_path": "docs/still-works.md", "content": "# Works\n"},
        )
        return listed, new_result, old_result

    listed, new_result, old_result = with_client(server, body)

    assert set(listed) == DEFAULT_NAMES | {"list_workspace_services"}
    new_schema = listed["list_workspace_services"].input_schema
    assert new_schema["additionalProperties"] is False and "prefix" in new_schema["properties"]
    assert payload(new_result) == {"services": ["payments-service"]}
    assert payload(old_result)["outcome"] == "created"
    assert _digest(real_files) == before, "adding a tool must not edit server.py or any default tool module"


def test_underscore_modules_are_not_registered(workspace: Workspace, tools_copy: tuple[str, Path]) -> None:
    name, folder = tools_copy
    (folder / "_helpers.py").write_text("raise RuntimeError('must never be imported')\n", encoding="utf-8")
    build_server(workspace, tools_package=name)  # would raise if the module were imported


def test_a_broken_tool_module_fails_startup_naming_the_module(
    workspace: Workspace, tools_copy: tuple[str, Path]
) -> None:
    name, folder = tools_copy
    (folder / "broken_tool.py").write_text("import module_that_does_not_exist\n", encoding="utf-8")
    with pytest.raises(ToolModuleError, match="broken_tool"):
        build_server(workspace, tools_package=name)


def test_a_module_without_register_fails_startup_naming_the_module(
    workspace: Workspace, tools_copy: tuple[str, Path]
) -> None:
    name, folder = tools_copy
    (folder / "forgot_register.py").write_text("VALUE = 1\n", encoding="utf-8")
    with pytest.raises(ToolModuleError, match="forgot_register"):
        build_server(workspace, tools_package=name)
