"""Spec: the agent source names no MCP tool, imports no actions code, and has no routing of its own."""
from __future__ import annotations

import ast
import re
from pathlib import Path

from tests.agent.helpers import real_mcp_tool_names

SRC = Path(__file__).resolve().parents[2] / "src" / "ecosystem_assistant"
AGENT_PACKAGE = SRC / "agent"
KNOWLEDGE_PACKAGE = SRC / "knowledge"
LLM_PACKAGE = SRC / "llm"
ACTIONS_PACKAGE = SRC / "actions"

FORBIDDEN_FOR_THE_AGENT = ("ecosystem_assistant.actions",)
FORBIDDEN_PROVIDERS = ("anthropic", "openai", "litellm", "cohere", "mistralai", "google")
# Files that hold the routing: they must not look at the words of the person's message.
ROUTING_FILES = ("graph.py", "agent.py")


def imports_of(root: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
            if isinstance(node, ast.Import):
                found += [(path.name, alias.name) for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.append((path.name, node.module))
    return found


def test_the_agent_package_does_not_import_the_actions_package() -> None:
    offenders = [f"{f}: imports {n}" for f, n in imports_of(AGENT_PACKAGE) if n.startswith(FORBIDDEN_FOR_THE_AGENT)]
    assert offenders == []


def test_the_agent_package_uses_no_model_provider_besides_ollama() -> None:
    offenders = [f"{f}: imports {n}" for f, n in imports_of(AGENT_PACKAGE) if n.split(".")[0] in FORBIDDEN_PROVIDERS]
    assert offenders == []


def test_no_mcp_tool_name_appears_in_the_agent_source(tmp_path: Path) -> None:
    names = real_mcp_tool_names(tmp_path)
    assert len(names) >= 3
    source = "\n".join(p.read_text(encoding="utf-8") for p in sorted(AGENT_PACKAGE.rglob("*.py")))
    found = [name for name in names if re.search(rf"\b{re.escape(name)}\b", source)]
    assert found == [], f"the agent must not name MCP tools, but its source mentions {found}"


def test_the_routing_files_do_not_inspect_the_text_of_messages() -> None:
    """No regular expressions and no text normalization where the loop and the turn are written."""
    problems: list[str] = []
    for name in ROUTING_FILES:
        tree = ast.parse((AGENT_PACKAGE / name).read_text(encoding="utf-8"), filename=name)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                problems += [f"{name}: imports {m}" for m in modules if m.split(".")[0] == "re"]
            if isinstance(node, ast.Attribute) and node.attr in {"lower", "casefold", "startswith", "find"}:
                problems.append(f"{name}: calls .{node.attr}() at line {node.lineno}")
    assert problems == []


def test_the_knowledge_side_and_the_model_layer_do_not_import_the_agent() -> None:
    for package in (KNOWLEDGE_PACKAGE, LLM_PACKAGE, ACTIONS_PACKAGE):
        offenders = [f"{f}: imports {n}" for f, n in imports_of(package) if n.startswith("ecosystem_assistant.agent")]
        assert offenders == [], package.name
