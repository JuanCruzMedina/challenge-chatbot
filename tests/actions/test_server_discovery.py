"""Spec: tools are discoverable with correct MCP schemas; errors vs conflicts."""
from __future__ import annotations

from typing import Any

from ecosystem_assistant.actions.server import build_server
from ecosystem_assistant.actions.workspace import Workspace
from tests.actions.helpers import payload, with_client

EXPECTED = {"add_document", "update_document", "mark_document_obsolete"}


def _tools(workspace: Workspace) -> dict[str, Any]:
    async def body(client):
        return {t.name: t for t in (await client.list_tools()).tools}

    return with_client(build_server(workspace), body)


def _call(workspace: Workspace, name: str, args: dict[str, Any]) -> Any:
    async def body(client):
        return await client.call_tool(name, args)

    return with_client(build_server(workspace), body)


def test_default_tools_are_listed(workspace: Workspace) -> None:
    assert set(_tools(workspace)) == EXPECTED


def test_each_tool_has_a_description_and_a_closed_object_schema(workspace: Workspace) -> None:
    for name, tool in _tools(workspace).items():
        assert tool.description and len(tool.description) > 60, name
        assert "Do NOT use" in tool.description, f"{name} must say when not to use it"
        schema = tool.input_schema
        assert schema["type"] == "object", name
        assert schema["properties"], name
        assert schema.get("additionalProperties") is False, name


def test_required_lists_match_the_mandatory_arguments(workspace: Workspace) -> None:
    tools = _tools(workspace)
    assert set(tools["add_document"].input_schema["required"]) == {"service", "doc_path", "content"}
    assert set(tools["update_document"].input_schema["required"]) == {"service", "doc_path", "old_text", "new_text"}
    mark = tools["mark_document_obsolete"].input_schema
    assert set(mark["required"]) == {"service", "doc_path", "reason"}
    assert "replaced_by" in mark["properties"] and "replaced_by" not in mark["required"]


def test_unknown_arguments_are_rejected(workspace: Workspace) -> None:
    result = _call(
        workspace, "add_document",
        {"service": "payments-service", "doc_path": "docs/x.md", "content": "c", "surprise": 1},
    )
    assert result.is_error is True


def test_invalid_input_is_an_error_that_names_the_argument(workspace: Workspace) -> None:
    bad_slug = _call(workspace, "add_document", {"service": "Bad Slug", "doc_path": "docs/x.md", "content": "c"})
    assert bad_slug.is_error is True and "service" in bad_slug.content[0].text

    ghost = _call(workspace, "add_document", {"service": "ghost-service", "doc_path": "docs/x.md", "content": "c"})
    assert ghost.is_error is True and "ghost-service" in ghost.content[0].text

    unsafe = _call(workspace, "add_document", {"service": "payments-service", "doc_path": "../x.md", "content": "c"})
    assert unsafe.is_error is True and "doc_path" in unsafe.content[0].text


def test_a_conflict_is_a_normal_result_not_an_error(workspace: Workspace) -> None:
    result = _call(
        workspace, "update_document",
        {"service": "payments-service", "doc_path": "docs/api-v1.md", "old_text": "not in the file", "new_text": "x"},
    )
    assert result.is_error is False
    assert payload(result)["outcome"] == "conflict"


def test_a_successful_call_is_not_an_error(workspace: Workspace) -> None:
    result = _call(
        workspace, "add_document",
        {"service": "payments-service", "doc_path": "docs/created.md", "content": "# Created\n"},
    )
    assert result.is_error is False
    assert payload(result)["outcome"] == "created"
