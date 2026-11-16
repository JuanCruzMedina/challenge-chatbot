"""Documentation tools: add, update (with conflict detection) and mark obsolete.

The three ``*_document`` / ``set_obsolete`` functions hold the behavior and are tested
directly. ``register`` publishes them as MCP tools; the server calls it for every module
in this package (design.md D-2). Nothing here reads the index, the graph or an LLM.
"""
from __future__ import annotations

import json
import re
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ecosystem_assistant.actions.workspace import Workspace, WorkspaceError, validate_relative_md

NOT_INDEXED_NOTE = (
    "Written to the documentation sources. It becomes searchable only after the next ingestion run."
)
_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_OBSOLETE_LINE = re.compile(r"(?m)^status:\s*obsolete\s*$")


# --- behavior -----------------------------------------------------------------------

def create_document(ws: Workspace, service: str, doc_path: str, content: str) -> dict[str, Any]:
    target = ws.resolve_doc(service, doc_path)
    if not isinstance(content, str) or not content.strip():
        raise WorkspaceError("content must not be empty")
    if target.exists():
        raise WorkspaceError(
            f"{doc_path!r} already exists for service {service!r}. Use update_document to change it."
        )
    ws.write_atomic(target, content)
    ws.audit("add_document", service, doc_path)
    return {"outcome": "created", "service": service, "doc_path": doc_path, "note": NOT_INDEXED_NOTE}


def replace_in_document(ws: Workspace, service: str, doc_path: str, old_text: str, new_text: str) -> dict[str, Any]:
    target = ws.resolve_doc(service, doc_path)
    if not isinstance(old_text, str) or old_text == "":
        raise WorkspaceError("old_text must not be empty: quote the exact passage to replace")
    if not target.is_file():
        raise WorkspaceError(
            f"{doc_path!r} does not exist for service {service!r}. Use add_document to create it."
        )
    text = target.read_bytes().decode("utf-8")
    occurrences = text.count(old_text)
    if occurrences != 1:
        reason = "text not found" if occurrences == 0 else "text not unique"
        return {
            "outcome": "conflict",
            "reason": reason,
            "occurrences": occurrences,
            "service": service,
            "doc_path": doc_path,
            "hint": (
                "Nothing was written. The document changed since it was read, or the quoted passage is "
                "ambiguous. Tell the user, then retry with the exact current text (include more context "
                "if it was not unique)."
            ),
        }
    ws.write_atomic(target, text.replace(old_text, new_text, 1))
    ws.audit("update_document", service, doc_path)
    return {"outcome": "updated", "service": service, "doc_path": doc_path, "note": NOT_INDEXED_NOTE}


def set_obsolete(
    ws: Workspace, service: str, doc_path: str, reason: str, replaced_by: str | None
) -> dict[str, Any]:
    target = ws.resolve_doc(service, doc_path)
    if not isinstance(reason, str) or not reason.strip():
        raise WorkspaceError("reason must not be empty")
    if replaced_by is not None:
        validate_relative_md(replaced_by, "replaced_by")
    if not target.is_file():
        raise WorkspaceError(f"{doc_path!r} does not exist for service {service!r}.")

    text = target.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    front = _FRONT_MATTER.match(text)
    if front and _OBSOLETE_LINE.search(front.group(1)):
        return {"outcome": "already_obsolete", "service": service, "doc_path": doc_path}

    lines = ["status: obsolete", f"obsolete_reason: {json.dumps(reason.strip(), ensure_ascii=False)}"]
    if replaced_by is not None:
        lines.append(f"replaced_by: {json.dumps(replaced_by, ensure_ascii=False)}")
    if front:
        block = f"---{newline}{front.group(1)}{newline}{newline.join(lines)}{newline}---{newline}"
        updated = block + text[front.end():]
    else:
        updated = f"---{newline}{newline.join(lines)}{newline}---{newline}" + text
    ws.write_atomic(target, updated)
    ws.audit("mark_document_obsolete", service, doc_path)
    return {"outcome": "marked_obsolete", "service": service, "doc_path": doc_path, "note": NOT_INDEXED_NOTE}


# --- MCP tools ----------------------------------------------------------------------

Service = Annotated[
    str,
    Field(
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="Service slug, e.g. 'payments-service'. Must be an existing service.",
    ),
]
DocPath = Annotated[
    str,
    Field(min_length=4, description="Path of the markdown file inside the service, e.g. 'docs/api-v2.md'. Relative, ends in .md, no '..'."),
]


def register(server: MCPServer, workspace: Workspace) -> None:
    @server.tool(
        description=(
            "Create a NEW markdown document for a service in the documentation sources. Use it when the "
            "user asks to add, write or create documentation (a runbook, guide, ADR, API page) that does "
            "not exist yet. Do NOT use it to change an existing document (use update_document), to mark "
            "one obsolete (use mark_document_obsolete), or to answer questions about documentation. "
            "The new document becomes searchable only after the next ingestion run."
        )
    )
    def add_document(
        service: Service,
        doc_path: DocPath,
        content: Annotated[str, Field(min_length=1, description="Full markdown content of the new document.")],
    ) -> dict[str, Any]:
        return create_document(workspace, service, doc_path, content)

    @server.tool(
        description=(
            "Replace one passage inside an EXISTING document. Use it when the user asks to correct, edit "
            "or update documentation. old_text must be copied exactly from the document and must appear "
            "exactly once. If the text is no longer there (someone else changed the document) or appears "
            "more than once, the tool writes nothing and returns outcome 'conflict': tell the user and "
            "retry with the current exact text. Do NOT use it to create files (use add_document) or to "
            "answer questions about documentation."
        )
    )
    def update_document(
        service: Service,
        doc_path: DocPath,
        old_text: Annotated[str, Field(min_length=1, description="Exact passage to replace, copied verbatim.")],
        new_text: Annotated[str, Field(description="Replacement text (may be empty to delete the passage).")],
    ) -> dict[str, Any]:
        return replace_in_document(workspace, service, doc_path, old_text, new_text)

    @server.tool(
        description=(
            "Flag an existing document as obsolete by adding 'status: obsolete' to its front matter. Use it "
            "when the user says a document is outdated, deprecated or replaced by another. It does not "
            "delete the document or change its body, and marking twice changes nothing. Do NOT use it to "
            "edit content (use update_document) or to answer questions about documentation."
        )
    )
    def mark_document_obsolete(
        service: Service,
        doc_path: DocPath,
        reason: Annotated[str, Field(min_length=1, description="Why the document is obsolete.")],
        replaced_by: Annotated[
            str | None, Field(description="Optional path of the document that replaces it, e.g. 'docs/api-v2.md'.")
        ] = None,
    ) -> dict[str, Any]:
        return set_obsolete(workspace, service, doc_path, reason, replaced_by)
