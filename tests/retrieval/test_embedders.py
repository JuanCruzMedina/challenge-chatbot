"""Spec: embedders are interchangeable and recorded; the MiniLM model is never downloaded silently."""
from __future__ import annotations

import builtins
import math
import socket
from pathlib import Path

import pytest

from ecosystem_assistant.knowledge.retrieval.embedders import (
    MODEL_FILES,
    HashingEmbedder,
    MiniLMEmbedder,
    ModelNotCachedError,
    embedder_by_name,
    model_is_cached,
)

RETRY_A = "Failed card payments are retried automatically with an increasing wait between attempts."
RETRY_B = "The payment retry policy: a failed charge is retried three times before it is reported."
TRACKING = "The vehicle position shows the latest GPS location of the truck on the dispatcher map."


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))  # both are unit vectors


# --- hashing embedder ------------------------------------------------------------------

def test_equal_text_gives_equal_vectors_across_calls_and_instances() -> None:
    first = HashingEmbedder().embed([RETRY_A])[0]
    second = HashingEmbedder().embed([RETRY_A])[0]
    assert first == second
    assert HashingEmbedder().embed([RETRY_A, TRACKING])[0] == first  # batch position does not matter


def test_vectors_have_the_declared_size_and_unit_length() -> None:
    embedder = HashingEmbedder()
    vectors = embedder.embed([RETRY_A, TRACKING, ""])
    assert embedder.name == "hashing" and embedder.dim == 256
    for vector in vectors:
        assert len(vector) == 256
        assert math.isclose(math.sqrt(sum(x * x for x in vector)), 1.0, rel_tol=1e-9)


def test_related_texts_are_closer_than_unrelated_ones() -> None:
    a, b, c = HashingEmbedder().embed([RETRY_A, RETRY_B, TRACKING])
    assert cosine(a, b) > cosine(a, c)
    assert cosine(a, b) > cosine(b, c)


def test_embedding_needs_no_network_and_no_files(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the offline embedder must not use the network or open files")

    embedder = HashingEmbedder()
    with monkeypatch.context() as patch:
        patch.setattr(socket.socket, "connect", forbidden)
        patch.setattr(builtins, "open", forbidden)
        vectors = embedder.embed([RETRY_A, "another text"])
    assert len(vectors) == 2


def test_an_empty_batch_gives_an_empty_result() -> None:
    assert HashingEmbedder().embed([]) == []


# --- MiniLM embedder: never downloads silently --------------------------------------------

def _fake_cache(folder: Path) -> Path:
    onnx = folder / "onnx"
    onnx.mkdir(parents=True)
    for name in MODEL_FILES:
        (onnx / name).write_bytes(b"x")
    return folder


def test_a_model_is_cached_only_when_all_its_files_exist(tmp_path: Path) -> None:
    assert model_is_cached(tmp_path / "nothing") is False
    folder = _fake_cache(tmp_path / "full")
    assert model_is_cached(folder) is True
    (folder / "onnx" / "model.onnx").unlink()
    assert model_is_cached(folder) is False


def test_without_the_model_and_without_opt_in_creation_fails_and_downloads_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("nothing may be downloaded")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.delenv("ALLOW_MODEL_DOWNLOAD", raising=False)
    folder = tmp_path / "empty-cache"

    with pytest.raises(ModelNotCachedError) as exc:
        MiniLMEmbedder(model_dir=folder)

    assert "ALLOW_MODEL_DOWNLOAD=1" in str(exc.value)
    assert not folder.exists() or not any(folder.iterdir())


def test_the_opt_in_can_come_from_the_environment_or_the_argument(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ALLOW_MODEL_DOWNLOAD", raising=False)
    MiniLMEmbedder(model_dir=tmp_path / "a", allow_download=True)  # creation never downloads; embedding would

    monkeypatch.setenv("ALLOW_MODEL_DOWNLOAD", "1")
    MiniLMEmbedder(model_dir=tmp_path / "b")

    monkeypatch.setenv("ALLOW_MODEL_DOWNLOAD", "0")
    with pytest.raises(ModelNotCachedError):
        MiniLMEmbedder(model_dir=tmp_path / "c")


def test_with_the_model_cached_creation_needs_no_opt_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALLOW_MODEL_DOWNLOAD", raising=False)
    embedder = MiniLMEmbedder(model_dir=_fake_cache(tmp_path / "cache"))
    assert embedder.name == "minilm-l6-v2" and embedder.dim == 384


def test_embedders_are_chosen_by_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert embedder_by_name("hashing").name == "hashing"
    with pytest.raises(ValueError) as exc:
        embedder_by_name("gpt-embeddings")
    assert "hashing" in str(exc.value) and "minilm" in str(exc.value)
