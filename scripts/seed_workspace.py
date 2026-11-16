"""Prepare the documentation workspace from the committed (read-only) sample data.

Usage: uv run python scripts/seed_workspace.py
Honors DOCS_WORKSPACE (default: var/workspace). Running it again resets the workspace
to a fresh copy. It only deletes inside a workspace that it created itself (marker file).
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_REPOS = REPO_ROOT / "data" / "ecosystem" / "repos"
DEFAULT_WORKSPACE = REPO_ROOT / "var" / "workspace"
MARKER = ".seeded-workspace"


def seed(source: Path, dest: Path) -> None:
    """Copy ``source`` (the sample repos) to ``dest/repos``, replacing any previous copy."""
    repos = dest / "repos"
    marker = dest / MARKER
    if repos.exists() and not marker.exists():
        sys.exit(
            f"Refusing to overwrite {repos}: it was not created by this script "
            f"(no {MARKER} marker). Remove it yourself or choose another DOCS_WORKSPACE."
        )
    if repos.exists():
        shutil.rmtree(repos)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, repos)
    marker.write_text("created by scripts/seed_workspace.py\n", encoding="utf-8")


def main() -> int:
    dest = Path(os.environ.get("DOCS_WORKSPACE", DEFAULT_WORKSPACE))
    seed(SAMPLE_REPOS, dest)
    services = sorted(p.name for p in (dest / "repos").iterdir() if p.is_dir())
    print(f"Workspace ready at {dest} with services: {', '.join(services)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
