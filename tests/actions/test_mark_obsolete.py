"""Spec: Mark a document as obsolete."""
from __future__ import annotations

from pathlib import Path

import pytest

from ecosystem_assistant.actions.tools.documents import set_obsolete
from ecosystem_assistant.actions.workspace import Workspace, WorkspaceError


def _doc(workspace_root: Path) -> Path:
    return workspace_root / "repos" / "payments-service" / "docs" / "api-v1.md"


def test_front_matter_is_written_and_the_body_is_unchanged(workspace: Workspace, workspace_root: Path) -> None:
    body = _doc(workspace_root).read_text(encoding="utf-8")

    result = set_obsolete(
        workspace, "payments-service", "docs/api-v1.md", "Replaced by v2", "docs/api-v2.md"
    )

    text = _doc(workspace_root).read_text(encoding="utf-8")
    assert result["outcome"] == "marked_obsolete"
    assert text.startswith("---\nstatus: obsolete\n")
    head, _, rest = text.partition("\n---\n")
    assert 'obsolete_reason: "Replaced by v2"' in head
    assert 'replaced_by: "docs/api-v2.md"' in head
    assert rest == body


def test_replaced_by_is_optional(workspace: Workspace, workspace_root: Path) -> None:
    set_obsolete(workspace, "payments-service", "docs/api-v1.md", "No longer valid", None)
    text = _doc(workspace_root).read_text(encoding="utf-8")
    assert "status: obsolete" in text
    assert "replaced_by" not in text


def test_marking_twice_is_idempotent(workspace: Workspace, workspace_root: Path) -> None:
    set_obsolete(workspace, "payments-service", "docs/api-v1.md", "Replaced by v2", None)
    marked = _doc(workspace_root).read_bytes()

    result = set_obsolete(workspace, "payments-service", "docs/api-v1.md", "Different reason", "docs/x.md")

    assert result["outcome"] == "already_obsolete"
    assert _doc(workspace_root).read_bytes() == marked


def test_existing_front_matter_is_extended_not_duplicated(workspace: Workspace, workspace_root: Path) -> None:
    _doc(workspace_root).write_text("---\nowner: payments-team\n---\n# Body\n", encoding="utf-8")

    set_obsolete(workspace, "payments-service", "docs/api-v1.md", "Old", None)

    text = _doc(workspace_root).read_text(encoding="utf-8")
    assert text.count("---\n") == 2
    assert "owner: payments-team" in text and "status: obsolete" in text
    assert text.endswith("# Body\n")


def test_a_missing_document_is_rejected(workspace: Workspace) -> None:
    with pytest.raises(WorkspaceError, match="does not exist"):
        set_obsolete(workspace, "payments-service", "docs/nope.md", "Old", None)


@pytest.mark.parametrize("replaced_by", ["/abs/x.md", "../x.md", "docs/x.txt"])
def test_unsafe_replacement_path_is_rejected(workspace: Workspace, workspace_root: Path, replaced_by: str) -> None:
    before = _doc(workspace_root).read_bytes()
    with pytest.raises(WorkspaceError, match="replaced_by"):
        set_obsolete(workspace, "payments-service", "docs/api-v1.md", "Old", replaced_by)
    assert _doc(workspace_root).read_bytes() == before


def test_empty_reason_is_rejected(workspace: Workspace) -> None:
    with pytest.raises(WorkspaceError, match="reason"):
        set_obsolete(workspace, "payments-service", "docs/api-v1.md", "  ", None)
