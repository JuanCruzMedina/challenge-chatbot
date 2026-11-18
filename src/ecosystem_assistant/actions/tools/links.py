"""Set what an existing document is about (add-document-links-writing).

The new-document case is ``add_document(..., about=[...])``; this tool changes the links of a document that exists,
to add them, correct them or remove them. It changes the ``about`` field of the front matter and nothing else.
"""
from __future__ import annotations

from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ecosystem_assistant.actions.front_matter import get_about, set_about
from ecosystem_assistant.actions.tools.documents import DocPath, Service, unresolved_hint
from ecosystem_assistant.actions.workspace import Workspace, WorkspaceError


def link_document_names(ws: Workspace, service: str, doc_path: str, about: list[str]) -> dict[str, Any]:
    target = ws.resolve_doc(service, doc_path)
    if not target.is_file():
        raise WorkspaceError(f"{doc_path!r} does not exist for service {service!r}.")
    text = target.read_bytes().decode("utf-8")
    resolved, unresolved = ws.resolve_names(about)
    ws.write_atomic(target, set_about(text, resolved))
    ws.audit("link_document", service, doc_path)
    result: dict[str, Any] = {"outcome": "linked", "service": service, "doc_path": doc_path, "about": resolved,
                              "previous": get_about(text), "unresolved": unresolved}
    if unresolved:
        result["hint"] = unresolved_hint(unresolved)
    return result


def register(server: MCPServer, workspace: Workspace) -> None:
    @server.tool(
        description=(
            "Set what an EXISTING document is about: the services, APIs or events it concerns. The list REPLACES the "
            "one the document has (an empty list removes it) and the result returns the previous list, so a "
            "mistake can be undone. Use it when the person asks to link, relink or unlink a document, or to correct "
            "what it is about. Names must be exact names of services, APIs or events; names that match nothing are "
            "not written and are listed as unresolved. It changes only that field of the front matter, never the "
            "text. Do NOT use it to create a document (add_document takes the same list) or to edit its text."
        )
    )
    def link_document(
        service: Service,
        doc_path: DocPath,
        about: Annotated[list[str], Field(description="Names of the services, APIs or events the document is about.")],
    ) -> dict[str, Any]:
        return link_document_names(workspace, service, doc_path, about)
