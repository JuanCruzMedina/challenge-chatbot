"""Documentation tools: add, update (with conflict detection) and mark obsolete.

The three ``*_document`` / ``set_obsolete`` functions hold the behavior and are tested
directly. ``register`` publishes them as MCP tools; the server calls it for every module
in this package (design.md D-2). Nothing here reads the index, the graph or an LLM.
"""
from __future__ import annotations

import difflib
import json
import re
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ecosystem_assistant.actions.front_matter import set_about
from ecosystem_assistant.actions.workspace import Workspace, WorkspaceError, validate_relative_md

NOT_INDEXED_NOTE = (
    "Written to the documentation sources. It becomes searchable only after the next ingestion run."
)
_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_OBSOLETE_LINE = re.compile(r"(?m)^status:\s*obsolete\s*$")


# --- behavior -----------------------------------------------------------------------

def _preview(service: str, doc_path: str, before: str, after: str) -> dict[str, Any]:
    """What an edit would change, as a diff. Nothing is written."""
    diff = "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                        fromfile=f"a/{doc_path}", tofile=f"b/{doc_path}"))
    return {
        "outcome": "needs_confirmation", "service": service, "doc_path": doc_path, "diff": diff,
        "hint": ("Nothing was written. Show this change to the person. If they agree, call this tool again with the "
                 "same arguments and confirmed=true."),
    }


def unresolved_hint(unresolved: list[str]) -> str:
    return ("These names match no service, API or event of the workspace and were not written: "
            f"{', '.join(unresolved)}. Use the exact names (ask the person if you cannot tell) and set them with "
            "the link tool.")


def create_document(ws: Workspace, service: str, doc_path: str, content: str,
                    about: list[str] | None = None) -> dict[str, Any]:
    target = ws.resolve_doc(service, doc_path)
    if not isinstance(content, str) or not content.strip():
        raise WorkspaceError("content must not be empty")
    if target.exists():
        raise WorkspaceError(
            f"{doc_path!r} already exists for service {service!r}. Use update_document to change it."
        )
    resolved: list[str] = []
    unresolved: list[str] = []
    if about is not None:
        resolved, unresolved = ws.resolve_names(about)
        content = set_about(content, resolved)
    ws.write_atomic(target, content)
    ws.audit("add_document", service, doc_path)
    result: dict[str, Any] = {"outcome": "created", "service": service, "doc_path": doc_path, "note": NOT_INDEXED_NOTE}
    if about is not None:
        result.update({"about": resolved, "unresolved": unresolved})
        if unresolved:
            result["hint"] = unresolved_hint(unresolved)
    return result


def replace_in_document(ws: Workspace, service: str, doc_path: str, old_text: str, new_text: str,
                        confirmed: bool = False) -> dict[str, Any]:
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
    updated = text.replace(old_text, new_text, 1)
    if ws.confirm_edits and not confirmed:
        return _preview(service, doc_path, text, updated)
    ws.write_atomic(target, updated)
    ws.audit("update_document", service, doc_path)
    return {"outcome": "updated", "service": service, "doc_path": doc_path, "note": NOT_INDEXED_NOTE}


def append_document(ws: Workspace, service: str, doc_path: str, text: str) -> dict[str, Any]:
    """Add ``text`` at the end of a document, or create the document; the old text never has to be quoted."""
    target = ws.resolve_doc(service, doc_path)
    if not isinstance(text, str) or not text.strip():
        raise WorkspaceError("text must not be empty")
    if target.is_file():
        current = target.read_bytes().decode("utf-8")
        newline = "\r\n" if "\r\n" in current else "\n"
        base = current if current.endswith(newline) else current + newline
        separator = newline if base.strip() else ""
        updated = base + separator + text.strip().replace("\r\n", "\n").replace("\n", newline) + newline
        outcome = "appended"
    else:
        updated = text.strip() + "\n"
        outcome = "created"
    ws.write_atomic(target, updated)
    ws.audit("append_to_document", service, doc_path)
    return {"outcome": outcome, "service": service, "doc_path": doc_path, "note": NOT_INDEXED_NOTE}


def set_obsolete(
    ws: Workspace, service: str, doc_path: str, reason: str, replaced_by: str | None, confirmed: bool = False
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
    if ws.confirm_edits and not confirmed:
        return _preview(service, doc_path, text, updated)
    ws.write_atomic(target, updated)
    ws.audit("mark_document_obsolete", service, doc_path)
    return {"outcome": "marked_obsolete", "service": service, "doc_path": doc_path, "note": NOT_INDEXED_NOTE}


# --- MCP tools ----------------------------------------------------------------------

Confirmed = Annotated[
    bool,
    Field(description=("Only when the tool answered 'needs_confirmation': set it to true to repeat the same call "
                       "after the person has seen the preview and agreed. Otherwise leave it out.")),
]
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


PREVIEW_NOTE = (
    "This server asks for confirmation: call it directly with the change (do not describe it or ask permission "
    "first); the first call writes nothing and returns a preview (outcome 'needs_confirmation'). Show that preview "
    "to the person and, once they agree, repeat the same call with confirmed=true. "
)


def register(server: MCPServer, workspace: Workspace) -> None:
    preview_note = PREVIEW_NOTE if workspace.confirm_edits else ""

    @server.tool(
        description=(
            "Create a NEW markdown document for a service in the documentation sources. Use it when the "
            "user asks to add, write or create documentation (a runbook, guide, ADR, API page) that does "
            "not exist yet. Do NOT use it to change an existing document (use update_document), to mark "
            "one obsolete (use mark_document_obsolete), or to answer questions about documentation. "
            "The new document becomes searchable only after the next ingestion run. Say what the document is "
            "about with `about`: the exact names of the services, APIs or events it concerns; names that match "
            "nothing are not written and come back as unresolved."
        )
    )
    def add_document(
        service: Service,
        doc_path: DocPath,
        content: Annotated[str, Field(min_length=1, description="Full markdown content of the new document.")],
        about: Annotated[
            list[str] | None,
            Field(description="Exact names of the services, APIs or events this document is about, e.g. "
                              "['payments-service', 'payments-api']. Leave it out only when it is about none."),
        ] = None,
    ) -> dict[str, Any]:
        return create_document(workspace, service, doc_path, content, about)

    @server.tool(
        description=(
            "Add text at the END of a markdown document, or create the document if it does not exist yet. "
            "Use it to record a new fact (an owner, a note, a decision) when the user asks to add or write "
            "something down: nothing has to be quoted from the old text. Do NOT use it to change or remove "
            "existing text (use update_document), to mark a document obsolete, or to answer questions "
            "about documentation. Only markdown files of an existing service are accepted. The text "
            "becomes searchable only after the next ingestion run."
        )
    )
    def append_to_document(
        service: Service,
        doc_path: DocPath,
        text: Annotated[str, Field(min_length=1, description="Markdown text to add at the end of the document.")],
    ) -> dict[str, Any]:
        return append_document(workspace, service, doc_path, text)

    @server.tool(
        description=(
            "Replace one passage inside an EXISTING document. Use it when the user asks to correct, edit "
            "or update documentation. old_text must be copied exactly from the document and must appear "
            "exactly once. If the text is no longer there (someone else changed the document) or appears "
            "more than once, the tool writes nothing and returns outcome 'conflict': tell the user and "
            "retry with the current exact text. " + preview_note + "Do NOT use it to create files (use "
            "add_document) or to answer questions about documentation."
        )
    )
    def update_document(
        service: Service,
        doc_path: DocPath,
        old_text: Annotated[str, Field(min_length=1, description="Exact passage to replace, copied verbatim.")],
        new_text: Annotated[str, Field(description="Replacement text (may be empty to delete the passage).")],
        confirmed: Confirmed = False,
    ) -> dict[str, Any]:
        return replace_in_document(workspace, service, doc_path, old_text, new_text, confirmed)

    @server.tool(
        description=(
            "Flag an existing document as obsolete by adding 'status: obsolete' to its front matter. Use it "
            "when the user says a document is outdated, deprecated or replaced by another. It does not "
            "delete the document or change its body, and marking twice changes nothing. " + preview_note +
            "Do NOT use it to edit content (use update_document) or to answer questions about documentation."
        )
    )
    def mark_document_obsolete(
        service: Service,
        doc_path: DocPath,
        reason: Annotated[str, Field(min_length=1, description="Why the document is obsolete.")],
        replaced_by: Annotated[
            str | None, Field(description="Optional path of the document that replaces it, e.g. 'docs/api-v2.md'.")
        ] = None,
        confirmed: Confirmed = False,
    ) -> dict[str, Any]:
        return set_obsolete(workspace, service, doc_path, reason, replaced_by, confirmed)
