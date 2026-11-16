"""Shared fixtures: a throwaway workspace so no test touches the committed sample data."""
from __future__ import annotations

from pathlib import Path

import pytest

from ecosystem_assistant.actions.workspace import Workspace


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    docs = root / "repos" / "payments-service" / "docs"
    docs.mkdir(parents=True)
    (docs / "api-v1.md").write_text("# payments-api v1\n\nv1 does not support automatic retries.\n", encoding="utf-8")
    notif = root / "repos" / "notifications-service" / "docs"
    notif.mkdir(parents=True)
    (notif / "runbook-delayed-emails.md").write_text("# Runbook: delayed emails\n", encoding="utf-8")
    return root


@pytest.fixture
def audit_file(tmp_path: Path) -> Path:
    return tmp_path / "audit" / "actions.jsonl"


@pytest.fixture
def workspace(workspace_root: Path, audit_file: Path) -> Workspace:
    return Workspace(root=workspace_root, audit_file=audit_file)
