"""Spec: the terminal chat has no routing of its own."""
from __future__ import annotations

import ast
from pathlib import Path

CHAT_PACKAGE = Path(__file__).resolve().parents[2] / "src" / "ecosystem_assistant" / "chat"
FORBIDDEN_IMPORTS = ("ecosystem_assistant.actions", "ecosystem_assistant.knowledge", "re")
TEXT_INSPECTION = {"lower", "casefold", "startswith", "endswith", "find", "split", "__contains__"}


def sources() -> list[tuple[str, ast.AST]]:
    return [(p.name, ast.parse(p.read_text(encoding="utf-8"), filename=str(p))) for p in sorted(CHAT_PACKAGE.glob("*.py"))]


def test_the_chat_package_imports_neither_the_actions_nor_the_knowledge_side() -> None:
    offenders = []
    for name, tree in sources():
        for node in ast.walk(tree):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else [])
            offenders += [f"{name}: imports {m}" for m in modules
                          if m == "re" or m.startswith(FORBIDDEN_IMPORTS[:2])]
    assert offenders == []


def test_the_chat_package_does_not_inspect_the_text_of_messages() -> None:
    """The only comparison of typed text allowed is `line == EXIT_COMMAND`; no string methods that look inside it."""
    offenders = [f"{name}: .{node.attr}() at line {node.lineno}"
                 for name, tree in sources() for node in ast.walk(tree)
                 if isinstance(node, ast.Attribute) and node.attr in TEXT_INSPECTION]
    assert offenders == []
