"""Safe access to the documentation workspace (paths, atomic writes, audit log).

Layout: ``<root>/repos/<service>/...``. Every path a tool touches is resolved here and
must stay inside its service folder. Nothing in this module reads the index, the
knowledge graph or any LLM (design.md D-3, D-6, D-7, D-8).
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import yaml
from mcp.server.mcpserver.exceptions import ToolError

# src/ecosystem_assistant/actions/workspace.py -> repository root
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WORKSPACE = REPO_ROOT / "var" / "workspace"
DEFAULT_AUDIT_FILE = REPO_ROOT / "var" / "audit" / "actions.jsonl"

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class WorkspaceError(ToolError):
    """A failure the caller can fix. It reaches the model with its message."""


@dataclass(frozen=True)
class Workspace:
    root: Path
    audit_file: Path
    confirm_edits: bool = False                      # edits and obsolete marks are only previewed until confirmed
    allowed_services: frozenset[str] | None = None   # None: every service may be written

    @classmethod
    def from_env(cls) -> "Workspace":
        """The server's settings. Confirmation is on unless ``ACTIONS_CONFIRM_EDITS=off``."""
        allowed = [s.strip() for s in os.environ.get("ACTIONS_ALLOWED_SERVICES", "").split(",") if s.strip()]
        return cls(
            root=Path(os.environ.get("DOCS_WORKSPACE", DEFAULT_WORKSPACE)),
            audit_file=Path(os.environ.get("ACTIONS_AUDIT_FILE", DEFAULT_AUDIT_FILE)),
            confirm_edits=os.environ.get("ACTIONS_CONFIRM_EDITS", "on").strip().lower() != "off",
            allowed_services=frozenset(allowed) if allowed else None,
        )

    # --- services -------------------------------------------------------------------

    @property
    def repos_dir(self) -> Path:
        return self.root / "repos"

    def list_services(self) -> list[str]:
        if not self.repos_dir.is_dir():
            return []
        return sorted(p.name for p in self.repos_dir.iterdir() if p.is_dir())

    def service_dir(self, service: str) -> Path:
        if not isinstance(service, str) or not SLUG.fullmatch(service):
            raise WorkspaceError(
                f"service must be a lowercase slug (letters, digits and hyphens): {service!r}"
            )
        candidate = self.repos_dir / service
        if not candidate.is_dir():
            valid = ", ".join(self.list_services()) or "none"
            raise WorkspaceError(f"service {service!r} does not exist in the workspace. Valid services: {valid}")
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.repos_dir.resolve()):
            raise WorkspaceError(f"service {service!r} resolves outside the workspace")
        return resolved

    # --- names a document can be about ----------------------------------------------

    def known_entities(self) -> set[str]:
        """The services of the workspace and the APIs and events their manifests declare."""
        names = set(self.list_services())
        for manifest in sorted(self.repos_dir.glob("*/service.yaml")) if self.repos_dir.is_dir() else []:
            try:
                data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            if not isinstance(data, dict):
                continue
            for entry in data.get("provides_apis") or []:
                if isinstance(entry, dict) and entry.get("id"):
                    names.add(str(entry["id"]))
            for field in ("consumes_apis", "publishes_events", "subscribes_events"):
                names.update(str(item) for item in data.get(field) or [])
        return names

    def resolve_names(self, names: list[str]) -> tuple[list[str], list[str]]:
        """Split ``names`` into those that match a known entity and those that do not (both sorted, no repeats)."""
        known = self.known_entities()
        cleaned = sorted({str(n).strip() for n in names if str(n).strip()})
        return [n for n in cleaned if n in known], [n for n in cleaned if n not in known]

    # --- documents ------------------------------------------------------------------

    def resolve_doc(self, service: str, doc_path: str) -> Path:
        base = self.service_dir(service)
        if self.allowed_services is not None and service not in self.allowed_services:
            raise WorkspaceError(
                f"this session may only change documents of: {', '.join(sorted(self.allowed_services))}. "
                f"{service!r} is not one of them; nothing was written."
            )
        validate_relative_md(doc_path)
        parts = PurePosixPath(doc_path).parts
        if parts[:2] == ("repos", service):
            inner = PurePosixPath(*parts[2:]).as_posix() if len(parts) > 2 else ""
            raise WorkspaceError(
                f"doc_path {doc_path!r} starts with the workspace folder of the service. Use the path inside the "
                f"service instead: {inner!r}"
            )
        resolved = (base / doc_path).resolve()
        if not resolved.is_relative_to(base):
            raise WorkspaceError(f"doc_path {doc_path!r} resolves outside the service folder")
        return resolved

    @staticmethod
    def write_atomic(target: Path, text: str) -> None:
        """Write ``text`` to ``target`` so that a failure never leaves a partial file."""
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".tmp-", suffix=".part")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, target)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

    # --- audit log ------------------------------------------------------------------

    def audit(self, action: str, service: str, path: str) -> None:
        entry = {
            "action": action,
            "service": service,
            "path": path,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def validate_relative_md(value: str, name: str = "doc_path") -> None:
    """Check that ``value`` is a safe relative path to a markdown file; errors name ``name``."""
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceError(f"{name} must be a non-empty relative path ending in .md")
    if "\\" in value or "\x00" in value:
        raise WorkspaceError(f"{name} must use forward slashes only: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise WorkspaceError(f"{name} must be relative, not absolute: {value!r}")
    if ".." in path.parts:
        raise WorkspaceError(f"{name} must not contain '..': {value!r}")
    if value.endswith("/") or not path.name.endswith(".md") or path.name == ".md":
        raise WorkspaceError(f"{name} must be a file ending in .md: {value!r}")
