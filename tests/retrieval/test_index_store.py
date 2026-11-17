"""Spec: the index records its embedder, refuses another, has telemetry off and lives outside the data."""
from __future__ import annotations

from pathlib import Path

import pytest

from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import IndexMismatchError, RetrievalIndex
from tests.data.helpers import SAMPLE


class OtherEmbedder(HashingEmbedder):
    name = "other-embedder"
    dim = 256


class WiderEmbedder(HashingEmbedder):
    name = "hashing"
    dim = 512


def test_a_new_index_is_empty_and_can_be_reopened(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    first = RetrievalIndex(directory, HashingEmbedder())
    assert first.stored_versions() == {}
    assert first.embedder.name == "hashing"

    reopened = RetrievalIndex(directory, HashingEmbedder())
    assert reopened.stored_versions() == {}


def test_an_index_refuses_a_different_embedder_and_says_to_rebuild(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    RetrievalIndex(directory, HashingEmbedder())

    with pytest.raises(IndexMismatchError) as exc:
        RetrievalIndex(directory, OtherEmbedder())

    message = str(exc.value)
    assert "hashing" in message and "other-embedder" in message and "rebuild" in message.lower()


def test_the_same_embedder_name_with_another_vector_size_is_also_refused(tmp_path: Path) -> None:
    RetrievalIndex(tmp_path / "index", HashingEmbedder())
    with pytest.raises(IndexMismatchError):
        RetrievalIndex(tmp_path / "index", WiderEmbedder())


def test_recreating_replaces_the_index_so_another_embedder_can_be_used(tmp_path: Path) -> None:
    directory = tmp_path / "index"
    RetrievalIndex(directory, HashingEmbedder())

    fresh = RetrievalIndex.recreate(directory, OtherEmbedder())

    assert fresh.embedder.name == "other-embedder"
    assert RetrievalIndex(directory, OtherEmbedder()).stored_versions() == {}


def test_telemetry_is_disabled(tmp_path: Path) -> None:
    assert RetrievalIndex(tmp_path / "index", HashingEmbedder()).telemetry_enabled is False


def test_the_location_is_configurable_and_outside_the_data_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VECTOR_INDEX_DIR", str(tmp_path / "from-env"))
    assert RetrievalIndex(embedder=HashingEmbedder()).directory == tmp_path / "from-env"
    assert (tmp_path / "from-env").is_dir()

    monkeypatch.delenv("VECTOR_INDEX_DIR")
    default = RetrievalIndex.default_directory()
    assert default.parts[-2:] == ("var", "index")
    assert SAMPLE not in default.parents and default != SAMPLE
