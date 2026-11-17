"""Spec: a documentation ticket can be created (add-ticket-tool)."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest

from ecosystem_assistant.actions.server import build_server
from ecosystem_assistant.actions.tools.tickets import create_ticket
from ecosystem_assistant.actions.workspace import Workspace, WorkspaceError
from ecosystem_assistant.knowledge.retrieval.documents import discover_documents
from tests.actions.helpers import with_client


def test_tickets_get_the_next_number_with_their_content(
    workspace: Workspace, workspace_root: Path, audit_file: Path
) -> None:
    first = create_ticket(workspace, "payments-service", "Document retries", "Explain the retry policy.", "high")
    second = create_ticket(workspace, "payments-service", "Fix the API page", "It lists a removed field.")

    assert (first["ticket_id"], second["ticket_id"]) == ("DOC-0001", "DOC-0002")
    assert first["path"] == "tickets/DOC-0001.md"
    text = (workspace_root / "tickets" / "DOC-0001.md").read_text(encoding="utf-8")
    assert text.startswith("---\nid: DOC-0001\nservice: payments-service\n")
    for line in ("title: \"Document retries\"", "priority: high", "status: open"):
        assert line in text
    assert text.rstrip().endswith("Explain the retry policy.")
    assert "priority: normal" in (workspace_root / "tickets" / "DOC-0002.md").read_text(encoding="utf-8")
    entries = [json.loads(line) for line in audit_file.read_text(encoding="utf-8").splitlines()]
    assert [(e["action"], e["path"]) for e in entries] == [
        ("create_documentation_ticket", "tickets/DOC-0001.md"),
        ("create_documentation_ticket", "tickets/DOC-0002.md"),
    ]


def test_a_ticket_never_goes_inside_the_repositories(workspace: Workspace, workspace_root: Path) -> None:
    before = sorted(p.relative_to(workspace_root).as_posix() for p in (workspace_root / "repos").rglob("*"))
    create_ticket(workspace, "payments-service", "T", "D")
    assert sorted(p.relative_to(workspace_root).as_posix() for p in (workspace_root / "repos").rglob("*")) == before


@pytest.mark.parametrize(
    ("service", "title", "description", "priority", "argument"),
    [
        ("ghost-service", "T", "D", "normal", "service"),
        ("payments-service", "  ", "D", "normal", "title"),
        ("payments-service", "two\nlines", "D", "normal", "title"),
        ("payments-service", "T", "  ", "normal", "description"),
        ("payments-service", "T", "D", "urgent", "priority"),
    ],
)
def test_invalid_input_is_refused_and_nothing_is_written(
    workspace: Workspace, workspace_root: Path, audit_file: Path,
    service: str, title: str, description: str, priority: str, argument: str,
) -> None:
    with pytest.raises(WorkspaceError, match=argument):
        create_ticket(workspace, service, title, description, priority)

    assert not (workspace_root / "tickets").exists()
    assert not audit_file.exists()


def test_two_simultaneous_creations_never_share_a_number(workspace: Workspace, workspace_root: Path) -> None:
    results: list[dict[str, Any]] = []
    barrier = threading.Barrier(8)

    def make(n: int) -> None:
        barrier.wait()
        results.append(create_ticket(workspace, "payments-service", f"T{n}", "D"))

    threads = [threading.Thread(target=make, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ids = sorted(r["ticket_id"] for r in results)
    assert len(results) == 8 and ids == [f"DOC-{n:04d}" for n in range(1, 9)]
    assert len(list((workspace_root / "tickets").glob("DOC-*.md"))) == 8


def test_tickets_are_not_part_of_the_informational_sources(workspace: Workspace, workspace_root: Path) -> None:
    before = discover_documents(workspace_root)
    create_ticket(workspace, "payments-service", "T", "D")
    assert discover_documents(workspace_root) == before


def test_the_tool_has_a_correct_schema(workspace: Workspace) -> None:
    async def body(client):
        return {t.name: t for t in (await client.list_tools()).tools}

    tool = with_client(build_server(workspace), body)["create_documentation_ticket"]
    assert "Do NOT use" in tool.description and len(tool.description) > 60
    schema = tool.input_schema
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"service", "title", "description"}
    assert set(schema["properties"]) == {"service", "title", "description", "priority"}
