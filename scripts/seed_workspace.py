"""Prepare the writable workspace: a complete copy of the committed (read-only) sample ecosystem.

Usage: uv run python scripts/seed_workspace.py
Honors DOCS_WORKSPACE (default: var/workspace). The workspace is a full data root (company, clients, repos, ...), so
the actions server can write to it and the knowledge side (graph and index) can read it. Running it again resets
the known entries to a fresh copy; it never touches other files, and it only deletes inside a workspace that it
created itself (marker file).
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_ROOT = REPO_ROOT / "data" / "ecosystem"
DEFAULT_WORKSPACE = REPO_ROOT / "var" / "workspace"
MARKER = ".seeded-workspace"
# The only entries this script ever creates or deletes in the workspace.
ENTRIES = ("README.md", "company.yaml", "company", "clients", "repos", "prs")


def seed(source: Path, dest: Path) -> None:
    """Copy the known entries of ``source`` (the sample ecosystem) into ``dest``, replacing any previous copy."""
    present = [dest / name for name in ENTRIES if (dest / name).exists()]
    if present and not (dest / MARKER).exists():
        sys.exit(
            f"Refusing to overwrite {present[0]}: it was not created by this script "
            f"(no {MARKER} marker). Remove it yourself or choose another DOCS_WORKSPACE."
        )
    dest.mkdir(parents=True, exist_ok=True)
    for path in present:
        shutil.rmtree(path) if path.is_dir() else path.unlink()
    for name in ENTRIES:
        origin = source / name
        if origin.is_dir():
            shutil.copytree(origin, dest / name)
        elif origin.is_file():
            shutil.copy2(origin, dest / name)
    (dest / MARKER).write_text("created by scripts/seed_workspace.py\n", encoding="utf-8")


def main() -> int:
    dest = Path(os.environ.get("DOCS_WORKSPACE", DEFAULT_WORKSPACE))
    seed(SAMPLE_ROOT, dest)
    services = sorted(p.name for p in (dest / "repos").iterdir() if p.is_dir())
    print(f"Workspace ready at {dest} with services: {', '.join(services)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
