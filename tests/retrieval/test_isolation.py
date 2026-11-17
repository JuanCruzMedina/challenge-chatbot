"""Spec: the retrieval index is isolated, private and read-only on the data."""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from tests.data.helpers import SAMPLE

SRC = Path(__file__).resolve().parents[2] / "src" / "ecosystem_assistant" / "knowledge"
RETRIEVAL_PACKAGE = SRC / "retrieval"
GRAPH_PACKAGE = SRC / "graph"

FORBIDDEN_INTERNAL = (
    "ecosystem_assistant.actions",
    "ecosystem_assistant.agent",
    "ecosystem_assistant.ingestion",
)
FORBIDDEN_EXTERNAL = (
    "mcp", "anthropic", "openai", "ollama", "langchain", "langchain_core", "langchain_anthropic",
    "langchain_ollama", "langgraph", "sentence_transformers", "faiss", "httpx", "requests", "aiohttp",
    "urllib3", "socket",
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


def forbidden_in(root: Path, internal: tuple[str, ...], external: tuple[str, ...]) -> list[str]:
    return [
        f"{file}: imports {name}" for file, name in imports_of(root)
        if name.startswith(internal) or name.split(".")[0] in external
    ]


def test_the_retrieval_package_has_no_forbidden_imports() -> None:
    assert forbidden_in(RETRIEVAL_PACKAGE, FORBIDDEN_INTERNAL, FORBIDDEN_EXTERNAL) == []


def test_the_detector_flags_forbidden_imports(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "import openai\nfrom ecosystem_assistant.agent import loop\nimport requests\nfrom mcp import Client\n",
        encoding="utf-8",
    )
    (tmp_path / "fine.py").write_text("import json\nimport chromadb\nimport yaml\n", encoding="utf-8")

    assert forbidden_in(tmp_path, FORBIDDEN_INTERNAL, FORBIDDEN_EXTERNAL) == [
        "bad.py: imports openai",
        "bad.py: imports ecosystem_assistant.agent",
        "bad.py: imports requests",
        "bad.py: imports mcp",
    ]


def test_the_graph_stays_below_the_retrieval_in_the_layering() -> None:
    offenders = [f"{f}: imports {n}" for f, n in imports_of(GRAPH_PACKAGE)
                 if n.startswith("ecosystem_assistant.knowledge.retrieval")]
    assert offenders == []


def test_telemetry_is_off_and_the_index_lives_outside_the_data(tmp_path: Path) -> None:
    index = RetrievalIndex(tmp_path / "index", HashingEmbedder())
    assert index.telemetry_enabled is False
    assert SAMPLE not in index.directory.parents and index.directory != SAMPLE
    assert RetrievalIndex.default_directory().parts[-2:] == ("var", "index")


def _digest(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_building_syncing_and_searching_never_modify_the_data(tmp_path: Path) -> None:
    before = _digest(SAMPLE)
    index = RetrievalIndex(tmp_path / "index", HashingEmbedder())

    index.sync(SAMPLE)
    index.sync(SAMPLE)
    index.search("payments", k=5)
    index.search("vehicle", client="demo-logistics", include_obsolete=True)

    after = _digest(SAMPLE)
    assert len(before) == 37 and "company.yaml" in before  # a real data root, not an empty folder
    assert after == before
