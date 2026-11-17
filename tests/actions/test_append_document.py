"""Spec: append text to a document without quoting it (improve-search-and-edits)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ecosystem_assistant.actions.tools.documents import append_document
from ecosystem_assistant.actions.workspace import Workspace, WorkspaceError

DOC = ("payments-service", "docs/api-v1.md")


def _path(root: Path, service: str, doc_path: str) -> Path:
    return root / "repos" / service / doc_path


def test_appending_to_an_existing_document_keeps_it_and_adds_the_text(
    workspace: Workspace, workspace_root: Path, audit_file: Path
) -> None:
    target = _path(workspace_root, *DOC)
    before = target.read_text(encoding="utf-8")

    result = append_document(workspace, *DOC, "Product Owner: Leo Messi")

    assert target.read_text(encoding="utf-8") == before + "\nProduct Owner: Leo Messi\n"
    assert result["outcome"] == "appended"
    entries = [json.loads(line) for line in audit_file.read_text(encoding="utf-8").splitlines()]
    assert [(e["action"], e["service"], e["path"]) for e in entries] == [("append_to_document", *DOC)]


def test_a_document_without_a_final_newline_still_gets_a_clean_separation(
    workspace: Workspace, workspace_root: Path
) -> None:
    target = _path(workspace_root, *DOC)
    target.write_text("# Title\n\nbody", encoding="utf-8")

    append_document(workspace, *DOC, "more")

    assert target.read_text(encoding="utf-8") == "# Title\n\nbody\n\nmore\n"


def test_windows_line_endings_are_kept(workspace: Workspace, workspace_root: Path) -> None:
    target = _path(workspace_root, *DOC)
    target.write_bytes(b"# Title\r\n\r\nbody\r\n")

    append_document(workspace, *DOC, "more")

    assert target.read_bytes() == b"# Title\r\n\r\nbody\r\n\r\nmore\r\n"


def test_appending_to_a_missing_document_creates_it(workspace: Workspace, workspace_root: Path) -> None:
    result = append_document(workspace, "payments-service", "docs/team.md", "Product Owner: Leo Messi")

    assert _path(workspace_root, "payments-service", "docs/team.md").read_text(encoding="utf-8") == (
        "Product Owner: Leo Messi\n"
    )
    assert result["outcome"] == "created"


@pytest.mark.parametrize(
    ("service", "doc_path", "text", "argument"),
    [
        ("ghost-service", "docs/a.md", "x", "service"),
        ("payments-service", "../a.md", "x", "doc_path"),
        ("payments-service", "docs/a.txt", "x", "doc_path"),
        ("payments-service", "docs/a.md", "   ", "text"),
    ],
)
def test_invalid_input_is_refused_and_nothing_is_written(
    workspace: Workspace, workspace_root: Path, audit_file: Path, service: str, doc_path: str, text: str, argument: str
) -> None:
    before = sorted(p.relative_to(workspace_root).as_posix() for p in workspace_root.rglob("*"))

    with pytest.raises(WorkspaceError, match=argument):
        append_document(workspace, service, doc_path, text)

    assert sorted(p.relative_to(workspace_root).as_posix() for p in workspace_root.rglob("*")) == before
    assert not audit_file.exists()
