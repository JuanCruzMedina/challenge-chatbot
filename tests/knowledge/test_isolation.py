"""Spec: the graph is isolated from actions, agent, LLM clients and the network, and is read-only."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from ecosystem_assistant.knowledge.graph.build import build_graph
from tests.data.helpers import SAMPLE

GRAPH_PACKAGE = Path(__file__).resolve().parents[2] / "src" / "ecosystem_assistant" / "knowledge" / "graph"

FORBIDDEN_INTERNAL = (
    "ecosystem_assistant.actions",
    "ecosystem_assistant.agent",
    "ecosystem_assistant.ingestion",
)
FORBIDDEN_EXTERNAL = (
    "mcp", "anthropic", "openai", "ollama", "langchain", "langchain_core", "langchain_anthropic",
    "langchain_ollama", "langgraph", "chromadb", "sentence_transformers", "faiss",
    "httpx", "requests", "aiohttp", "urllib3", "socket",
)


def find_forbidden_imports(root: Path) -> list[str]:
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
                if name.startswith(FORBIDDEN_INTERNAL) or name.split(".")[0] in FORBIDDEN_EXTERNAL:
                    violations.append(f"{path.name}: imports {name}")
    return violations


def test_the_graph_package_has_no_forbidden_imports() -> None:
    assert find_forbidden_imports(GRAPH_PACKAGE) == []


def test_the_detector_flags_forbidden_imports(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "import anthropic\nfrom ecosystem_assistant.actions import server\nimport socket\nfrom mcp import Client\n",
        encoding="utf-8",
    )
    (tmp_path / "fine.py").write_text("import json\nimport networkx\nimport yaml\n", encoding="utf-8")
    assert find_forbidden_imports(tmp_path) == [
        "bad.py: imports anthropic",
        "bad.py: imports ecosystem_assistant.actions",
        "bad.py: imports socket",
        "bad.py: imports mcp",
    ]


def _digest(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_building_and_querying_never_modifies_the_data() -> None:
    before = _digest(SAMPLE)

    graph = build_graph(SAMPLE)
    graph.find_entities("payments")
    graph.client_overview("demo-grocery")
    graph.application_services("storefront")
    graph.service_owner("orders-service")
    graph.api_consumers("payments-api")
    graph.event_flow("order.created")
    graph.service_product_context("driver-service")
    graph.relation_path("tracking-service", "driver-service")
    graph.describe("payments-service")
    graph.obsolete_documents()
    graph.service_owner("ordres-service")  # a not-found result must not touch the data either

    after = _digest(SAMPLE)
    manifests = [name for name in before if name.startswith("repos/") and name.endswith("/service.yaml")]
    assert "company.yaml" in before and len(manifests) == 7  # a real data root, not an empty folder
    assert after == before
