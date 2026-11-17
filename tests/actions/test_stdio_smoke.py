"""Spec: the server runs offline with no API keys, over a real stdio subprocess."""
from __future__ import annotations

import asyncio
import os
import shutil
import socket
import sys
import time
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters

from ecosystem_assistant.actions.server import build_server
from ecosystem_assistant.actions.workspace import Workspace
from tests.actions.helpers import payload, with_client

SAMPLE_REPOS = Path(__file__).resolve().parents[2] / "data" / "ecosystem" / "repos"


def test_subprocess_over_stdio_lists_tools_and_calls_one(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    shutil.copytree(SAMPLE_REPOS, root / "repos")
    env = {
        # Only what the server needs: no API keys, no proxy or network settings.
        "PATH": os.environ.get("PATH", ""),
        "DOCS_WORKSPACE": str(root),
        "ACTIONS_AUDIT_FILE": str(tmp_path / "audit.jsonl"),
    }
    params = StdioServerParameters(command=sys.executable, args=["-m", "ecosystem_assistant.actions.server"], env=env)

    async def run() -> tuple[set[str], dict]:
        async with Client(params) as client:
            names = {t.name for t in (await client.list_tools()).tools}
            result = await client.call_tool(
                "add_document",
                {"service": "notifications-service", "doc_path": "docs/smoke.md", "content": "# Smoke\n"},
            )
            return names, payload(result)

    started = time.monotonic()
    names, outcome = asyncio.run(run())
    elapsed = time.monotonic() - started

    assert names == {"add_document", "append_to_document", "create_documentation_ticket", "update_document", "mark_document_obsolete"}
    assert outcome["outcome"] == "created"
    assert (root / "repos" / "notifications-service" / "docs" / "smoke.md").read_text(encoding="utf-8") == "# Smoke\n"
    assert elapsed < 10, f"smoke test took {elapsed:.1f}s"


def test_a_tool_call_needs_no_network(workspace: Workspace, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the action server tried to open a network connection")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    async def body(client: Client) -> dict:
        result = await client.call_tool(
            "add_document",
            {"service": "payments-service", "doc_path": "docs/offline.md", "content": "# Offline\n"},
        )
        return payload(result)

    assert with_client(build_server(workspace), body)["outcome"] == "created"
