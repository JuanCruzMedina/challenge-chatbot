from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ecosystem_assistant.knowledge.graph.build import build_graph
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from tests.data.fixture import build_dataset
from tests.data.helpers import SAMPLE


@pytest.fixture(scope="session")
def sample_graph() -> KnowledgeGraph:
    """The graph of the committed sample data (read-only, shared by the whole session)."""
    return build_graph(SAMPLE)


@pytest.fixture
def sample_copy(tmp_path: Path) -> Path:
    """A modifiable copy of the committed sample data."""
    target = tmp_path / "ecosystem"
    shutil.copytree(SAMPLE, target)
    return target


@pytest.fixture
def fx_root(tmp_path: Path) -> Path:
    """The small synthetic dataset (company, two clients, three applications, three services)."""
    return build_dataset(tmp_path / "synthetic")


@pytest.fixture
def fx_graph(fx_root: Path) -> KnowledgeGraph:
    return build_graph(fx_root)
