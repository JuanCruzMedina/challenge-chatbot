"""Spec: a new document can say what it is about; the links of an existing one can be set (add-document-links-writing)."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from ecosystem_assistant.actions.front_matter import get_about, set_about
from ecosystem_assistant.actions.server import build_server
from ecosystem_assistant.actions.tools.documents import create_document
from ecosystem_assistant.actions.tools.links import link_document_names
from ecosystem_assistant.actions.workspace import Workspace, WorkspaceError
from tests.actions.helpers import payload, with_client

MANIFEST = """name: payments-service
owner_team: payments-team
tech_lead: Valeria Sosa
provides_apis:
  - id: payments-api
    version: v1
    status: active
consumes_apis:
  - orders-api
publishes_events:
  - payment.confirmed
subscribes_events:
  - order.created
"""


@pytest.fixture
def ws(workspace: Workspace, workspace_root: Path) -> Workspace:
    (workspace_root / "repos" / "payments-service" / "service.yaml").write_text(MANIFEST, encoding="utf-8")
    return workspace


def _doc(root: Path, service: str = "payments-service", path: str = "docs/note.md") -> str:
    return (root / "repos" / service / path).read_text(encoding="utf-8")


def _front(text: str) -> dict:
    return yaml.safe_load(text.split("---\n")[1])


# --- the front matter helper ---------------------------------------------------------------------------------------

def test_about_is_added_to_a_document_without_front_matter() -> None:
    out = set_about("# T\n\nBody\n", ["payments-api"])
    assert out == '---\nabout: ["payments-api"]\n---\n# T\n\nBody\n' and get_about(out) == ["payments-api"]


def test_about_joins_the_existing_front_matter_without_touching_other_fields() -> None:
    out = set_about("---\nstatus: obsolete\nreplaced_by: x.md\n---\n# T\n", ["a-b"])
    assert _front(out) == {"status": "obsolete", "replaced_by": "x.md", "about": ["a-b"]} and out.endswith("# T\n")


def test_a_one_line_and_a_multi_line_list_are_replaced() -> None:
    one = set_about('---\nabout: [old-one]\ntitle: T\n---\nBody\n', ["new-one"])
    multi = set_about("---\ntitle: T\nabout:\n  - old-one\n  - old-two\nowner: me\n---\nBody\n", ["new-one"])
    dash = set_about("---\nabout:\n- old-one\ntitle: T\n---\nBody\n", ["new-one"])

    assert _front(one) == {"title": "T", "about": ["new-one"]}
    assert _front(multi) == {"title": "T", "owner": "me", "about": ["new-one"]}
    assert _front(dash) == {"title": "T", "about": ["new-one"]}


def test_an_empty_list_removes_the_field_and_an_empty_front_matter() -> None:
    assert set_about("---\nabout: [a]\n---\nBody\n", []) == "Body\n"
    assert _front(set_about("---\nabout: [a]\ntitle: T\n---\nBody\n", [])) == {"title": "T"}


def test_the_line_ending_style_is_kept() -> None:
    out = set_about("---\r\ntitle: T\r\n---\r\nBody\r\n", ["a-b"])
    assert "\n" not in out.replace("\r\n", "") and "about" in out


# --- add_document with about ---------------------------------------------------------------------------------------

def test_known_names_are_written_in_the_new_document(ws: Workspace, workspace_root: Path) -> None:
    result = create_document(ws, "payments-service", "docs/note.md", "# Note\n\nText.\n",
                             ["payments-service", "payments-api", "payment.confirmed", "order.created"])

    assert result["outcome"] == "created" and result["unresolved"] == []
    assert result["about"] == ["order.created", "payment.confirmed", "payments-api", "payments-service"]
    assert _front(_doc(workspace_root))["about"] == result["about"]
    assert _doc(workspace_root).endswith("# Note\n\nText.\n")


def test_unknown_names_are_dropped_and_reported(ws: Workspace, workspace_root: Path) -> None:
    result = create_document(ws, "payments-service", "docs/note.md", "# Note\n", ["payments-api", "ghost-service"])

    assert result["about"] == ["payments-api"] and result["unresolved"] == ["ghost-service"]
    assert "ghost-service" in result["hint"] and _front(_doc(workspace_root))["about"] == ["payments-api"]


def test_a_document_with_its_own_front_matter_keeps_it(ws: Workspace, workspace_root: Path) -> None:
    create_document(ws, "payments-service", "docs/note.md", "---\ntitle: Mine\n---\n# Note\n", ["payments-api"])
    assert _front(_doc(workspace_root)) == {"title": "Mine", "about": ["payments-api"]}


def test_without_about_the_file_is_exactly_the_content(ws: Workspace, workspace_root: Path) -> None:
    result = create_document(ws, "payments-service", "docs/note.md", "# Note\n")
    assert _doc(workspace_root) == "# Note\n" and "unresolved" not in result


# --- link_document -------------------------------------------------------------------------------------------------

def test_links_are_replaced_and_the_previous_ones_returned(ws: Workspace, workspace_root: Path, audit_file: Path) -> None:
    create_document(ws, "payments-service", "docs/note.md", "# Note\n\nBody\n", ["payments-service"])

    result = link_document_names(ws, "payments-service", "docs/note.md", ["payments-api", "ghost"])

    assert result["previous"] == ["payments-service"] and result["about"] == ["payments-api"]
    assert result["unresolved"] == ["ghost"] and result["outcome"] == "linked"
    assert _front(_doc(workspace_root))["about"] == ["payments-api"] and _doc(workspace_root).endswith("# Note\n\nBody\n")
    actions = [json.loads(line)["action"] for line in audit_file.read_text(encoding="utf-8").splitlines()]
    assert actions == ["add_document", "link_document"]


def test_an_empty_list_removes_the_links(ws: Workspace, workspace_root: Path) -> None:
    create_document(ws, "payments-service", "docs/note.md", "# Note\n", ["payments-api"])
    result = link_document_names(ws, "payments-service", "docs/note.md", [])
    assert result["about"] == [] and _doc(workspace_root) == "# Note\n"


def test_a_missing_document_is_an_error(ws: Workspace) -> None:
    with pytest.raises(WorkspaceError):
        link_document_names(ws, "payments-service", "docs/missing.md", ["payments-api"])


def test_the_scope_applies_to_the_new_tool(ws: Workspace) -> None:
    limited = replace(ws, allowed_services=frozenset({"notifications-service"}))
    with pytest.raises(WorkspaceError):
        link_document_names(limited, "payments-service", "docs/api-v1.md", ["payments-api"])


def test_the_server_discovers_the_new_tool_with_a_closed_schema(ws: Workspace) -> None:
    async def body(client):
        return {t.name: t for t in (await client.list_tools()).tools}

    tools = with_client(build_server(ws), body)

    schema = tools["link_document"].input_schema
    assert set(schema["required"]) == {"service", "doc_path", "about"} and schema["additionalProperties"] is False
    assert "about" in tools["add_document"].input_schema["properties"]
    assert "about" not in tools["add_document"].input_schema["required"]


def test_the_tool_runs_over_mcp(ws: Workspace, workspace_root: Path) -> None:
    async def body(client):
        return payload(await client.call_tool("add_document", {
            "service": "payments-service", "doc_path": "docs/note.md", "content": "# Note\n",
            "about": ["payments-api", "ghost-service"]}))

    result = with_client(build_server(ws), body)
    assert result["about"] == ["payments-api"] and result["unresolved"] == ["ghost-service"]
