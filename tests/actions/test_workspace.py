"""Workspace: safe paths, atomic writes and the audit log (spec: writes confined and audited)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ecosystem_assistant.actions.workspace import Workspace, WorkspaceError


# --- service validation -------------------------------------------------------------

@pytest.mark.parametrize("bad", ["", "Payments", "a/b", "..", "pay ments", "pay_ments"])
def test_service_must_be_a_lowercase_slug(workspace: Workspace, bad: str) -> None:
    with pytest.raises(WorkspaceError, match="service"):
        workspace.service_dir(bad)


def test_unknown_service_lists_the_valid_ones(workspace: Workspace) -> None:
    with pytest.raises(WorkspaceError) as exc:
        workspace.service_dir("ghost-service")
    message = str(exc.value)
    assert "service" in message
    assert "payments-service" in message and "notifications-service" in message


def test_known_service_resolves(workspace: Workspace, workspace_root: Path) -> None:
    assert workspace.service_dir("payments-service") == (workspace_root / "repos" / "payments-service").resolve()


# --- doc_path validation ------------------------------------------------------------

@pytest.mark.parametrize(
    "bad",
    ["", "/etc/passwd.md", "../x.md", "docs/../../x.md", "docs/readme.txt", "docs/readme", "docs\\a.md", "docs/"],
)
def test_doc_path_must_be_a_safe_relative_markdown_path(workspace: Workspace, bad: str) -> None:
    with pytest.raises(WorkspaceError, match="doc_path"):
        workspace.resolve_doc("payments-service", bad)


def test_valid_doc_path_resolves_inside_the_service(workspace: Workspace, workspace_root: Path) -> None:
    target = workspace.resolve_doc("payments-service", "docs/new-doc.md")
    assert target == (workspace_root / "repos" / "payments-service" / "docs" / "new-doc.md").resolve()


def test_symlink_escaping_the_workspace_is_rejected(workspace: Workspace, workspace_root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = workspace_root / "repos" / "payments-service" / "docs" / "escape"
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(WorkspaceError, match="doc_path"):
        workspace.resolve_doc("payments-service", "docs/escape/stolen.md")
    assert not (outside / "stolen.md").exists()


# --- atomic write ---------------------------------------------------------------------

def test_write_creates_parent_folders_and_the_file(workspace: Workspace) -> None:
    target = workspace.resolve_doc("payments-service", "docs/deep/new.md")
    workspace.write_atomic(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_failed_write_leaves_original_intact_and_no_temp_files(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = workspace.resolve_doc("payments-service", "docs/api-v1.md")
    original = target.read_text(encoding="utf-8")

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated failure during rename")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        workspace.write_atomic(target, "NEW CONTENT")
    monkeypatch.undo()

    assert target.read_text(encoding="utf-8") == original
    assert sorted(p.name for p in target.parent.iterdir()) == ["api-v1.md"]


# --- audit log ------------------------------------------------------------------------

def test_each_audit_call_appends_one_json_line(workspace: Workspace, audit_file: Path) -> None:
    workspace.audit("add_document", "payments-service", "docs/a.md")
    workspace.audit("update_document", "payments-service", "docs/a.md")
    lines = audit_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first, second = (json.loads(line) for line in lines)
    assert first["action"] == "add_document" and second["action"] == "update_document"
    for entry in (first, second):
        assert entry["service"] == "payments-service"
        assert entry["path"] == "docs/a.md"
        assert entry["timestamp"]


# --- settings -------------------------------------------------------------------------

def test_from_env_reads_configured_locations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DOCS_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("ACTIONS_AUDIT_FILE", str(tmp_path / "audit.jsonl"))
    ws = Workspace.from_env()
    assert ws.root == (tmp_path / "ws")
    assert ws.audit_file == (tmp_path / "audit.jsonl")


def test_from_env_defaults_are_under_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCS_WORKSPACE", raising=False)
    monkeypatch.delenv("ACTIONS_AUDIT_FILE", raising=False)
    ws = Workspace.from_env()
    assert ws.root.parts[-2:] == ("var", "workspace")
    assert ws.audit_file.parts[-3:] == ("var", "audit", "actions.jsonl")
