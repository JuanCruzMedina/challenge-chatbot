"""Spec: the flow is read-only and isolated from the actions server, the MCP SDK and other model providers."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from ecosystem_assistant.knowledge.flow.graph import InformationalFlow
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from ecosystem_assistant.llm.scripted import ScriptedLLM
from tests.data.helpers import SAMPLE

SRC = Path(__file__).resolve().parents[2] / "src" / "ecosystem_assistant"
FLOW_PACKAGE = SRC / "knowledge" / "flow"
LLM_PACKAGE = SRC / "llm"
ACTIONS_PACKAGE = SRC / "actions"

FORBIDDEN_INTERNAL = ("ecosystem_assistant.actions", "ecosystem_assistant.agent", "ecosystem_assistant.ingestion")
# The MCP SDK and every model provider except Ollama (the one allowed provider, and only inside the llm package).
FORBIDDEN_EXTERNAL = (
    "mcp", "anthropic", "openai", "litellm", "cohere", "mistralai", "google", "langchain_anthropic",
    "langchain_openai", "langchain_ollama", "sentence_transformers", "requests",
)


def imports_of(root: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
            if isinstance(node, ast.Import):
                found += [(path.name, alias.name) for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.append((path.name, node.module))
    return found


def forbidden_in(root: Path) -> list[str]:
    return [f"{f}: imports {n}" for f, n in imports_of(root)
            if n.startswith(FORBIDDEN_INTERNAL) or n.split(".")[0] in FORBIDDEN_EXTERNAL]


def test_the_flow_and_model_packages_have_no_forbidden_imports() -> None:
    assert forbidden_in(FLOW_PACKAGE) == []
    assert forbidden_in(LLM_PACKAGE) == []


def test_the_detector_flags_forbidden_imports(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "import anthropic\nfrom ecosystem_assistant.actions import server\nfrom mcp import Client\nimport openai\n",
        encoding="utf-8")
    (tmp_path / "fine.py").write_text("import ollama\nimport langgraph\nimport json\n", encoding="utf-8")

    assert forbidden_in(tmp_path) == [
        "bad.py: imports anthropic",
        "bad.py: imports ecosystem_assistant.actions",
        "bad.py: imports mcp",
        "bad.py: imports openai",
    ]


def test_only_the_llm_package_talks_to_ollama() -> None:
    offenders = [f"{f}: imports {n}" for f, n in imports_of(FLOW_PACKAGE) if n.split(".")[0] in {"ollama", "httpx"}]
    assert offenders == []
    assert any(n.split(".")[0] == "ollama" for _f, n in imports_of(LLM_PACKAGE))


def test_the_actions_server_imports_neither_the_flow_nor_the_model_layer() -> None:
    offenders = [f"{f}: imports {n}" for f, n in imports_of(ACTIONS_PACKAGE)
                 if n.startswith(("ecosystem_assistant.llm", "ecosystem_assistant.knowledge"))]
    assert offenders == []


def _digest(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_asking_questions_of_every_kind_never_modifies_the_data(
    sample_graph: KnowledgeGraph, sample_index: RetrievalIndex
) -> None:
    before = _digest(SAMPLE)
    script = [
        {"graph_queries": [{"method": "service_owner", "arguments": {"service": "tracking-service"}}]},
        {"answer": "tracking-team [K1]", "citations": ["K1"]},     # a graph question
        {"graph_queries": []}, {"answer": "see [D1]", "citations": ["D1"]},  # a document question
        {"graph_queries": []},                                      # an unknown question: no evidence
    ]
    flow = InformationalFlow(sample_graph, sample_index, ScriptedLLM(script), min_score=0.0)
    flow.ask("Who owns the tracking service?")
    flow.ask("What should I do when a vehicle disappears from the map?")
    unknown = InformationalFlow(sample_graph, sample_index, ScriptedLLM([{"graph_queries": []}]), min_score=1.01)
    assert unknown.ask("What is the capital of France?").status == "insufficient_evidence"

    manifests = [name for name in before if name.startswith("repos/") and name.endswith("/service.yaml")]
    assert len(manifests) == 7 and "company.yaml" in before
    assert _digest(SAMPLE) == before
