"""Spec: writes are audited and the committed sample data is never touched."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from ecosystem_assistant.actions.tools.documents import create_document, replace_in_document, set_obsolete
from ecosystem_assistant.actions.workspace import Workspace, WorkspaceError

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DATA = REPO_ROOT / "data" / "ecosystem"


def _digest(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_successful_writes_are_audited_in_order(workspace: Workspace, audit_file: Path) -> None:
    create_document(workspace, "payments-service", "docs/new.md", "# New\n\nold line\n")
    replace_in_document(workspace, "payments-service", "docs/new.md", "old line", "new line")
    set_obsolete(workspace, "payments-service", "docs/new.md", "Superseded", None)

    entries = [json.loads(line) for line in audit_file.read_text(encoding="utf-8").splitlines()]
    assert [e["action"] for e in entries] == ["add_document", "update_document", "mark_document_obsolete"]
    for entry in entries:
        assert entry["service"] == "payments-service"
        assert entry["path"] == "docs/new.md"
        assert entry["timestamp"]


def test_conflicts_errors_and_no_ops_add_no_audit_entry(workspace: Workspace, audit_file: Path) -> None:
    replace_in_document(workspace, "payments-service", "docs/api-v1.md", "text that is not there", "x")  # conflict
    for call in (
        lambda: create_document(workspace, "ghost-service", "docs/a.md", "x"),
        lambda: replace_in_document(workspace, "payments-service", "docs/nope.md", "a", "b"),
        lambda: set_obsolete(workspace, "payments-service", "docs/nope.md", "Old", None),
    ):
        try:
            call()
        except WorkspaceError:
            pass
    set_obsolete(workspace, "payments-service", "docs/api-v1.md", "Old", None)
    set_obsolete(workspace, "payments-service", "docs/api-v1.md", "Old", None)  # already obsolete: no-op

    entries = [json.loads(line) for line in audit_file.read_text(encoding="utf-8").splitlines()]
    assert [e["action"] for e in entries] == ["mark_document_obsolete"]


def test_committed_sample_data_is_never_touched(tmp_path: Path) -> None:
    before = _digest(SAMPLE_DATA)
    root = tmp_path / "ws"
    shutil.copytree(SAMPLE_DATA / "repos", root / "repos")
    ws = Workspace(root=root, audit_file=tmp_path / "audit.jsonl")

    create_document(ws, "orders-service", "docs/new.md", "# New\n")  # success
    replace_in_document(ws, "orders-service", "docs/api.md", "text that is not there", "x")  # conflict
    set_obsolete(ws, "orders-service", "docs/api.md", "Old", None)  # success
    try:
        create_document(ws, "orders-service", "../escape.md", "x")  # failure
    except WorkspaceError:
        pass

    assert _digest(SAMPLE_DATA) == before
    assert (root / "repos" / "orders-service" / "docs" / "new.md").exists()
