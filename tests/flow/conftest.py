from __future__ import annotations

from pathlib import Path

import pytest

from ecosystem_assistant.knowledge.graph.build import build_graph
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from tests.data.helpers import SAMPLE


@pytest.fixture(scope="session")
def sample_graph() -> KnowledgeGraph:
    """The graph of the committed sample data (read-only, shared by the whole session)."""
    return build_graph(SAMPLE)


@pytest.fixture(scope="session")
def sample_index(tmp_path_factory: pytest.TempPathFactory) -> RetrievalIndex:
    """An index of the committed data with the offline embedder (read-only use, shared by the session)."""
    index = RetrievalIndex(tmp_path_factory.mktemp("flow-index"), HashingEmbedder())
    index.sync(SAMPLE)
    return index
