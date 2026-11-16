"""Spec: Update a document with conflict detection."""
from __future__ import annotations

from pathlib import Path

import pytest

from ecosystem_assistant.actions.tools.documents import replace_in_document
from ecosystem_assistant.actions.workspace import Workspace, WorkspaceError

OLD = "v1 does not support automatic retries"


def _doc(workspace_root: Path) -> Path:
    return workspace_root / "repos" / "payments-service" / "docs" / "api-v1.md"


def test_a_passage_is_updated_and_the_rest_is_untouched(workspace: Workspace, workspace_root: Path) -> None:
    before = _doc(workspace_root).read_text(encoding="utf-8")

    result = replace_in_document(workspace, "payments-service", "docs/api-v1.md", OLD, "v1 is deprecated")

    after = _doc(workspace_root).read_text(encoding="utf-8")
    assert result["outcome"] == "updated"
    assert after == before.replace(OLD, "v1 is deprecated")
    assert after.startswith("# payments-api v1\n")


def test_conflict_when_the_passage_changed_since_it_was_read(workspace: Workspace, workspace_root: Path) -> None:
    _doc(workspace_root).write_text("# payments-api v1\n\nsomeone else rewrote this.\n", encoding="utf-8")
    before = _doc(workspace_root).read_bytes()

    result = replace_in_document(workspace, "payments-service", "docs/api-v1.md", OLD, "new text")

    assert result["outcome"] == "conflict"
    assert "not found" in result["reason"]
    assert _doc(workspace_root).read_bytes() == before


def test_conflict_when_the_passage_is_ambiguous(workspace: Workspace, workspace_root: Path) -> None:
    _doc(workspace_root).write_text(f"{OLD}.\n\nAgain: {OLD}.\n", encoding="utf-8")
    before = _doc(workspace_root).read_bytes()

    result = replace_in_document(workspace, "payments-service", "docs/api-v1.md", OLD, "new text")

    assert result["outcome"] == "conflict"
    assert "not unique" in result["reason"]
    assert _doc(workspace_root).read_bytes() == before


def test_missing_document_points_to_add_document(workspace: Workspace) -> None:
    with pytest.raises(WorkspaceError, match="add_document"):
        replace_in_document(workspace, "payments-service", "docs/nope.md", "a", "b")


def test_empty_old_text_is_rejected(workspace: Workspace) -> None:
    with pytest.raises(WorkspaceError, match="old_text"):
        replace_in_document(workspace, "payments-service", "docs/api-v1.md", "", "b")


def test_windows_line_endings_survive_an_update(workspace: Workspace, workspace_root: Path) -> None:
    _doc(workspace_root).write_bytes(b"# Title\r\n\r\nkeep me\r\nchange me\r\n")

    replace_in_document(workspace, "payments-service", "docs/api-v1.md", "change me", "changed")

    assert _doc(workspace_root).read_bytes() == b"# Title\r\n\r\nkeep me\r\nchanged\r\n"
