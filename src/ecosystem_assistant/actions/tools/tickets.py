"""Documentation tickets: a request to write or fix documentation, kept as a markdown file.

A ticket is an action record, not documentation: it lives in ``tickets/`` at the workspace root, outside ``repos/``,
so the informational flow never indexes it. This module is the demonstration that a tool is added to the server by
adding a file: nothing else in the server, and nothing in the agent, knows about it.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from ecosystem_assistant.actions.workspace import Workspace, WorkspaceError

PRIORITIES = ("low", "normal", "high")
_NUMBER = re.compile(r"DOC-(\d{4,})\.md\Z")
_ATTEMPTS = 20


def _next_number(folder: Path) -> int:
    numbers = [int(m.group(1)) for p in folder.glob("DOC-*.md") if (m := _NUMBER.fullmatch(p.name))] if folder.is_dir() else []
    return max(numbers, default=0) + 1


def _publish_new(target: Path, text: str) -> bool:
    """Write ``text`` to ``target`` only if it does not exist yet; never leaves a partial file. False if taken."""
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(tmp_name, target)  # fails when the number was taken in the meantime
        except FileExistsError:
            return False
        return True
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def create_ticket(
    ws: Workspace, service: str, title: str, description: str, priority: str = "normal"
) -> dict[str, Any]:
    ws.service_dir(service)  # an existing service, same check as the other tools
    if not isinstance(title, str) or not title.strip():
        raise WorkspaceError("title must not be empty")
    if "\n" in title or "\r" in title:
        raise WorkspaceError("title must be one line")
    if not isinstance(description, str) or not description.strip():
        raise WorkspaceError("description must not be empty")
    if priority not in PRIORITIES:
        raise WorkspaceError(f"priority must be one of {', '.join(PRIORITIES)}: {priority!r}")

    folder = ws.root / "tickets"
    folder.mkdir(parents=True, exist_ok=True)
    created = datetime.now(timezone.utc).date().isoformat()
    for _ in range(_ATTEMPTS):
        ticket_id = f"DOC-{_next_number(folder):04d}"
        text = (
            f"---\nid: {ticket_id}\nservice: {service}\ntitle: {json.dumps(title.strip(), ensure_ascii=False)}\n"
            f"priority: {priority}\nstatus: open\ncreated: {created}\n---\n\n{description.strip()}\n"
        )
        if _publish_new(folder / f"{ticket_id}.md", text):
            path = f"tickets/{ticket_id}.md"
            ws.audit("create_documentation_ticket", service, path)
            return {"outcome": "created", "ticket_id": ticket_id, "service": service, "path": path}
    raise WorkspaceError("could not reserve a ticket number; try again")


def register(server: MCPServer, workspace: Workspace) -> None:
    @server.tool(
        description=(
            "Open a documentation ticket: a request that someone writes or fixes documentation of a service "
            "later. Use it when the user asks to open, file or log a ticket or a to-do about missing or "
            "wrong documentation, instead of writing the documentation now. Do NOT use it to write or edit "
            "the documentation itself (use add_document, append_to_document or update_document), to mark a "
            "document obsolete, or to answer questions. The ticket is a file in tickets/ and is not searchable."
        )
    )
    def create_documentation_ticket(
        service: Annotated[
            str,
            Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
                  description="Service slug the ticket is about, e.g. 'payments-service'. Must be an existing service."),
        ],
        title: Annotated[str, Field(min_length=1, description="One-line summary of what is needed.")],
        description: Annotated[str, Field(min_length=1, description="What documentation is missing or wrong.")],
        priority: Annotated[Literal["low", "normal", "high"], Field(description="How urgent it is.")] = "normal",
    ) -> dict[str, Any]:
        return create_ticket(workspace, service, title, description, priority)
