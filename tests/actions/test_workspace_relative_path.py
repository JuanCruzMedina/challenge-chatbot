"""Spec: a workspace-relative path is rejected, not misread (fix-team-leads-and-doc-paths)."""
from __future__ import annotations

from pathlib import Path

import pytest

from ecosystem_assistant.actions.tools.documents import append_document, create_document, replace_in_document
from ecosystem_assistant.actions.workspace import Workspace, WorkspaceError

SERVICE = "payments-service"


def _files(root: Path) -> set[Path]:
    return {p for p in root.rglob("*") if p.is_file()}


def test_a_citation_path_is_rejected_and_nothing_is_written(workspace: Workspace, workspace_root: Path) -> None:
    before = _files(workspace_root)

    with pytest.raises(WorkspaceError) as caught:
        append_document(workspace, SERVICE, "repos/payments-service/docs/api-v1.md", "Product Owner: Leo Messi")

    assert "docs/api-v1.md" in str(caught.value) and "inside the service" in str(caught.value)
    assert _files(workspace_root) == before


@pytest.mark.parametrize("call", [
    lambda ws, path: create_document(ws, SERVICE, path, "x"),
    lambda ws, path: replace_in_document(ws, SERVICE, path, "a", "b"),
])
def test_every_write_tool_rejects_it(workspace: Workspace, call) -> None:
    with pytest.raises(WorkspaceError) as caught:
        call(workspace, "repos/payments-service/docs/new.md")
    assert "inside the service" in str(caught.value)


def test_a_path_inside_the_service_still_works(workspace: Workspace, workspace_root: Path) -> None:
    target = workspace_root / "repos" / SERVICE / "docs" / "api-v1.md"
    before = target.read_text(encoding="utf-8")

    append_document(workspace, SERVICE, "docs/api-v1.md", "Product Owner: Leo Messi")

    assert target.read_text(encoding="utf-8").startswith(before)
    assert "Leo Messi" in target.read_text(encoding="utf-8")


def test_another_services_prefix_is_not_confused_with_this_one(workspace: Workspace, workspace_root: Path) -> None:
    create_document(workspace, SERVICE, "repos/notes.md", "# Notes\n")  # a folder named repos inside the service

    assert (workspace_root / "repos" / SERVICE / "repos" / "notes.md").is_file()
