"""Spec: the package has no rule of its own (no string inspection of the PR text, no tool names)."""
from __future__ import annotations

import ast
import re
from pathlib import Path

from ecosystem_assistant.actions.server import build_server
from ecosystem_assistant.actions.workspace import Workspace
from tests.actions.helpers import with_client

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "ecosystem_assistant" / "pr_review"
FORBIDDEN_CALLS = {"lower", "casefold", "startswith", "endswith", "find", "index", "match", "search", "fullmatch"}


def problems(root: Path) -> list[str]:
    found: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                found += [f"{path.name}: imports {m}" for m in modules
                          if m.split(".")[0] == "re" or m.startswith("ecosystem_assistant.actions")]
            if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_CALLS:
                found.append(f"{path.name}: uses .{node.attr}() at line {node.lineno}")
            if isinstance(node, ast.Compare) and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
                found.append(f"{path.name}: tests membership at line {node.lineno}")
    return found


def test_the_package_inspects_no_text_and_imports_no_actions_code() -> None:
    assert problems(PACKAGE) == []


def test_the_check_detects_a_violation(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("import re\ndef f(pr):\n    return pr.title.lower()\n")
    assert len(problems(tmp_path)) == 2


def test_no_tool_of_the_server_is_named_in_the_package(tmp_path: Path) -> None:
    async def names(client):
        return [t.name for t in (await client.list_tools()).tools]

    tools = with_client(build_server(Workspace(root=tmp_path, audit_file=tmp_path / "a.jsonl")), names)
    source = "\n".join(p.read_text(encoding="utf-8") for p in sorted(PACKAGE.rglob("*.py")))
    assert tools and [t for t in tools if re.search(rf"\b{re.escape(t)}\b", source)] == []
