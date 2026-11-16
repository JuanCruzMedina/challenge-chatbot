"""Spec: Add a document."""
from __future__ import annotations

from pathlib import Path

import pytest

from ecosystem_assistant.actions.tools.documents import create_document
from ecosystem_assistant.actions.workspace import Workspace, WorkspaceError


def test_a_new_document_is_created(workspace: Workspace, workspace_root: Path) -> None:
    result = create_document(workspace, "notifications-service", "docs/runbook-new.md", "# New runbook\n\nSteps.\n")

    target = workspace_root / "repos" / "notifications-service" / "docs" / "runbook-new.md"
    assert target.read_text(encoding="utf-8") == "# New runbook\n\nSteps.\n"
    assert result["outcome"] == "created"
    assert result["service"] == "notifications-service"
    assert result["doc_path"] == "docs/runbook-new.md"


def test_an_existing_document_is_not_overwritten(workspace: Workspace, workspace_root: Path) -> None:
    target = workspace_root / "repos" / "payments-service" / "docs" / "api-v1.md"
    before = target.read_bytes()

    with pytest.raises(WorkspaceError, match="update_document"):
        create_document(workspace, "payments-service", "docs/api-v1.md", "replacement")

    assert target.read_bytes() == before


@pytest.mark.parametrize(
    ("service", "doc_path", "argument"),
    [
        ("ghost-service", "docs/a.md", "service"),
        ("Payments", "docs/a.md", "service"),
        ("payments-service", "/abs/a.md", "doc_path"),
        ("payments-service", "../a.md", "doc_path"),
        ("payments-service", "docs/a.txt", "doc_path"),
    ],
)
def test_unknown_service_or_unsafe_path_is_rejected(
    workspace: Workspace, workspace_root: Path, service: str, doc_path: str, argument: str
) -> None:
    before = sorted(p.relative_to(workspace_root).as_posix() for p in workspace_root.rglob("*"))

    with pytest.raises(WorkspaceError, match=argument):
        create_document(workspace, service, doc_path, "content")

    assert sorted(p.relative_to(workspace_root).as_posix() for p in workspace_root.rglob("*")) == before


def test_empty_content_is_rejected(workspace: Workspace) -> None:
    with pytest.raises(WorkspaceError, match="content"):
        create_document(workspace, "payments-service", "docs/empty.md", "   ")
