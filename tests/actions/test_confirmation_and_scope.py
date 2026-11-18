"""Spec: edits are previewed and confirmed; a session can be limited to some services (confirm-edits-and-limit-scope)."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from ecosystem_assistant.actions.tools.documents import (
    append_document, create_document, replace_in_document, set_obsolete,
)
from ecosystem_assistant.actions.workspace import Workspace, WorkspaceError

DOC = ("payments-service", "docs/api-v1.md")
OLD = "v1 does not support automatic retries."


@pytest.fixture
def asking(workspace: Workspace) -> Workspace:
    return replace(workspace, confirm_edits=True)


def _text(root: Path) -> str:
    return (root / "repos" / DOC[0] / DOC[1]).read_text(encoding="utf-8")


def test_an_unconfirmed_edit_is_only_previewed(asking: Workspace, workspace_root: Path, audit_file: Path) -> None:
    before = _text(workspace_root)

    result = replace_in_document(asking, *DOC, OLD, "v1 retries up to 3 times.")

    assert result["outcome"] == "needs_confirmation"
    assert "-v1 does not support" in result["diff"] and "+v1 retries up to 3 times." in result["diff"]
    assert "confirmed" in result["hint"] and "Nothing was written" in result["hint"]
    assert _text(workspace_root) == before and not audit_file.exists()


def test_a_confirmed_edit_is_written(asking: Workspace, workspace_root: Path, audit_file: Path) -> None:
    result = replace_in_document(asking, *DOC, OLD, "v1 retries up to 3 times.", confirmed=True)

    assert result["outcome"] == "updated" and "retries up to 3 times" in _text(workspace_root)
    assert len(audit_file.read_text(encoding="utf-8").splitlines()) == 1


def test_an_obsolete_mark_is_previewed_then_written(asking: Workspace, workspace_root: Path, audit_file: Path) -> None:
    before = _text(workspace_root)

    preview = set_obsolete(asking, *DOC, "replaced", "docs/api-v2.md")
    assert preview["outcome"] == "needs_confirmation" and "+status: obsolete" in preview["diff"]
    assert _text(workspace_root) == before and not audit_file.exists()

    done = set_obsolete(asking, *DOC, "replaced", "docs/api-v2.md", confirmed=True)
    assert done["outcome"] == "marked_obsolete" and "status: obsolete" in _text(workspace_root)


def test_creating_and_appending_are_not_asked(asking: Workspace, workspace_root: Path) -> None:
    assert create_document(asking, "payments-service", "docs/new.md", "# New\n")["outcome"] == "created"
    assert append_document(asking, *DOC, "A note.")["outcome"] == "appended"


def test_a_conflict_comes_before_the_preview(asking: Workspace) -> None:
    result = replace_in_document(asking, *DOC, "text that is not there", "x")
    assert result["outcome"] == "conflict"


def test_without_the_setting_edits_are_direct_as_before(workspace: Workspace) -> None:
    assert replace_in_document(workspace, *DOC, OLD, "new")["outcome"] == "updated"


def test_the_environment_sets_confirmation_and_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ACTIONS_CONFIRM_EDITS", raising=False)
    monkeypatch.delenv("ACTIONS_ALLOWED_SERVICES", raising=False)
    default = Workspace.from_env()
    assert default.confirm_edits is True and default.allowed_services is None

    monkeypatch.setenv("ACTIONS_CONFIRM_EDITS", "off")
    monkeypatch.setenv("ACTIONS_ALLOWED_SERVICES", "payments-service, orders-service")
    limited = Workspace.from_env()
    assert limited.confirm_edits is False
    assert limited.allowed_services == frozenset({"payments-service", "orders-service"})


def test_a_write_outside_the_scope_is_rejected_and_nothing_is_written(workspace: Workspace, workspace_root: Path) -> None:
    limited = replace(workspace, allowed_services=frozenset({"payments-service"}))
    before = sorted(workspace_root.rglob("*"))

    with pytest.raises(WorkspaceError) as caught:
        create_document(limited, "notifications-service", "docs/x.md", "# X\n")

    assert "payments-service" in str(caught.value)
    assert sorted(workspace_root.rglob("*")) == before


def test_every_write_tool_respects_the_scope(workspace: Workspace) -> None:
    limited = replace(workspace, allowed_services=frozenset({"payments-service"}))
    other = ("notifications-service", "docs/runbook-delayed-emails.md")
    for call in (lambda: append_document(limited, *other, "x"),
                 lambda: replace_in_document(limited, *other, "a", "b"),
                 lambda: set_obsolete(limited, *other, "old", None)):
        with pytest.raises(WorkspaceError):
            call()


def test_a_write_inside_the_scope_works(workspace: Workspace, workspace_root: Path) -> None:
    limited = replace(workspace, allowed_services=frozenset({"payments-service"}))
    assert create_document(limited, "payments-service", "docs/ok.md", "# Ok\n")["outcome"] == "created"


def _descriptions(ws: Workspace) -> dict[str, str]:
    from ecosystem_assistant.actions.server import build_server
    from tests.actions.helpers import with_client

    async def body(client):
        return {t.name: t.description for t in (await client.list_tools()).tools}

    return with_client(build_server(ws), body)


def test_the_descriptions_talk_about_the_preview_only_when_the_server_asks(workspace: Workspace, asking: Workspace) -> None:
    asks, direct = _descriptions(asking), _descriptions(workspace)

    for name in ("update_document", "mark_document_obsolete"):
        assert "needs_confirmation" in asks[name] and "ask permission" in asks[name].lower(), name
        assert "needs_confirmation" not in direct[name] and "preview" not in direct[name].lower(), name
