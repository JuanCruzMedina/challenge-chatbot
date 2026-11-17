"""The server can be started with another tools package and a quiet log (add-agent design.md D-7)."""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from ecosystem_assistant.actions import tools as default_tools
from ecosystem_assistant.actions.server import (
    DEFAULT_TOOLS_PACKAGE,
    build_server,
    log_level_from_env,
    tools_package_from_env,
)
from ecosystem_assistant.actions.workspace import Workspace
from tests.actions.test_extensibility import NEW_TOOL

DEFAULT_NAMES = {"add_document", "append_to_document", "create_documentation_ticket", "update_document", "mark_document_obsolete"}


def test_the_default_tools_package_is_the_real_one() -> None:
    assert tools_package_from_env({}) == DEFAULT_TOOLS_PACKAGE
    assert tools_package_from_env({"ACTIONS_TOOLS_PACKAGE": ""}) == DEFAULT_TOOLS_PACKAGE


def test_the_tools_package_can_be_chosen_by_the_environment() -> None:
    assert tools_package_from_env({"ACTIONS_TOOLS_PACKAGE": "my_tools.pkg"}) == "my_tools.pkg"


def test_the_log_level_is_quiet_by_default_and_can_be_changed() -> None:
    assert log_level_from_env({}) == "WARNING"
    assert log_level_from_env({"ACTIONS_LOG_LEVEL": "debug"}) == "DEBUG"


def test_an_invalid_log_level_is_rejected_by_name() -> None:
    with pytest.raises(ValueError, match="ACTIONS_LOG_LEVEL"):
        log_level_from_env({"ACTIONS_LOG_LEVEL": "loud"})


def test_the_server_is_built_with_the_given_log_level(workspace: Workspace) -> None:
    assert build_server(workspace).settings.log_level == "WARNING"
    assert build_server(workspace, log_level="ERROR").settings.log_level == "ERROR"


def _env(workspace_root: Path, tmp_path: Path, **extra: str) -> dict[str, str]:
    return {"PATH": os.environ.get("PATH", ""), "DOCS_WORKSPACE": str(workspace_root),
            "ACTIONS_AUDIT_FILE": str(tmp_path / "audit.jsonl"), **extra}


def test_a_stdio_server_started_with_another_package_lists_its_extra_tool(
    workspace_root: Path, tmp_path: Path
) -> None:
    package = tmp_path / "plugins" / "extra_tools_pkg"
    shutil.copytree(Path(default_tools.__file__).parent, package, ignore=shutil.ignore_patterns("__pycache__"))
    (package / "workspace_services.py").write_text(NEW_TOOL, encoding="utf-8")
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "ecosystem_assistant.actions.server"],
        env=_env(workspace_root, tmp_path, ACTIONS_TOOLS_PACKAGE="extra_tools_pkg",
                 PYTHONPATH=str(tmp_path / "plugins")),
    )

    async def run() -> tuple[set[str], str]:
        async with Client(params) as client:
            names = {t.name for t in (await client.list_tools()).tools}
            result = await client.call_tool("list_workspace_services", {"prefix": "pay"})
            return names, result.content[0].text

    names, text = asyncio.run(run())

    assert names == DEFAULT_NAMES | {"list_workspace_services"}
    assert "payments-service" in text


def test_an_unimportable_package_stops_the_start_and_names_it(workspace_root: Path, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ecosystem_assistant.actions.server"], input="", capture_output=True, text=True,
        env=_env(workspace_root, tmp_path, ACTIONS_TOOLS_PACKAGE="no_such_tools_package_zzz"), check=False, timeout=60,
    )
    assert result.returncode != 0
    assert "no_such_tools_package_zzz" in result.stderr
