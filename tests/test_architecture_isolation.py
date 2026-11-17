"""Spec: the action server is isolated from the informational flow and from any LLM."""
from __future__ import annotations

import ast
from pathlib import Path

ACTIONS_PACKAGE = Path(__file__).resolve().parents[1] / "src" / "ecosystem_assistant" / "actions"

# Informational flow, agent and ingestion packages of this project.
FORBIDDEN_INTERNAL = (
    "ecosystem_assistant.retrieval",
    "ecosystem_assistant.knowledge",
    "ecosystem_assistant.graph",
    "ecosystem_assistant.agent",
    "ecosystem_assistant.ingestion",
    "ecosystem_assistant.llm",
)
# Vector store, graph, embedding and LLM client libraries.
FORBIDDEN_EXTERNAL = (
    "anthropic", "openai", "ollama", "langchain", "langchain_core", "langchain_anthropic",
    "langchain_ollama", "langgraph", "chromadb", "networkx", "sentence_transformers",
    "faiss", "httpx", "requests",
)


def find_forbidden_imports(root: Path) -> list[str]:
    """Every import under ``root`` that points at the informational flow, an LLM client or a network library."""
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                top = name.split(".")[0]
                if name.startswith(FORBIDDEN_INTERNAL) or top in FORBIDDEN_EXTERNAL:
                    violations.append(f"{path.name}: imports {name}")
    return violations


def test_the_actions_package_has_no_informational_or_llm_imports() -> None:
    assert find_forbidden_imports(ACTIONS_PACKAGE) == []


def test_the_check_detects_a_forbidden_import(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "import openai\nfrom ecosystem_assistant.retrieval import index\nfrom chromadb import Client\n",
        encoding="utf-8",
    )
    (tmp_path / "fine.py").write_text("import json\nfrom pathlib import Path\n", encoding="utf-8")

    found = find_forbidden_imports(tmp_path)

    assert found == [
        "bad.py: imports openai",
        "bad.py: imports ecosystem_assistant.retrieval",
        "bad.py: imports chromadb",
    ]
