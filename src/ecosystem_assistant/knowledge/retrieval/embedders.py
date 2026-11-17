"""Embedders: turn text into vectors (design.md D-2, D-3).

``HashingEmbedder`` is deterministic and fully offline (tests, no-download use). ``MiniLMEmbedder``
wraps Chroma's ONNX MiniLM and never downloads its model unless the caller opted in.
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import unicodedata
from pathlib import Path
from typing import Protocol

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the this to was were will with".split()
)


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


# --- hashing embedder ------------------------------------------------------------------------

def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _stem(token: str) -> str:
    """A deliberately crude stemmer so that 'payments' and 'payment' meet; good enough for lexical hashing."""
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


class HashingEmbedder:
    """Signed feature hashing of word unigrams and bigrams into 256 dimensions, L2-normalized.

    Lexical only: it finds shared words, not paraphrases. It exists so that tests and offline runs
    need no model. It uses a stable hash (not Python's randomized ``hash``), so vectors repeat
    across runs and machines.
    """

    name = "hashing"
    dim = 256

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        tokens = [_stem(t) for t in _TOKEN.findall(_fold(text)) if t not in _STOPWORDS and len(t) > 1]
        vector = [0.0] * self.dim
        features = [(t, 1.0) for t in tokens] + [(f"{a} {b}", 0.5) for a, b in zip(tokens, tokens[1:])]
        for feature, weight in features:
            digest = int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")
            vector[digest % self.dim] += weight if (digest >> 63) & 1 else -weight
        norm = math.sqrt(sum(x * x for x in vector))
        if norm == 0.0:
            vector[0] = 1.0  # a text with no features still needs a valid unit vector
            return vector
        return [x / norm for x in vector]


# --- MiniLM embedder -----------------------------------------------------------------------

# Files that make Chroma consider the ONNX model cached (confirmed in task 1.2).
MODEL_FILES = ("config.json", "model.onnx", "special_tokens_map.json", "tokenizer_config.json",
               "tokenizer.json", "vocab.txt")
OPT_IN_VARIABLE = "ALLOW_MODEL_DOWNLOAD"
DEFAULT_MODEL_DIR = Path.home() / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2"


class ModelNotCachedError(RuntimeError):
    """The MiniLM model is not on this machine and downloading it was not authorized."""


def model_is_cached(model_dir: Path = DEFAULT_MODEL_DIR) -> bool:
    return all((Path(model_dir) / "onnx" / name).exists() for name in MODEL_FILES)


class MiniLMEmbedder:
    """all-MiniLM-L6-v2 on Chroma's ONNX runtime (English, 384 dimensions, no PyTorch)."""

    name = "minilm-l6-v2"
    dim = 384

    def __init__(self, model_dir: Path | None = None, allow_download: bool | None = None) -> None:
        self._model_dir = Path(model_dir) if model_dir is not None else DEFAULT_MODEL_DIR
        allowed = allow_download if allow_download is not None else os.environ.get(OPT_IN_VARIABLE) == "1"
        if not model_is_cached(self._model_dir) and not allowed:
            raise ModelNotCachedError(
                f"The MiniLM model is not cached in {self._model_dir} and downloading it (about 80 MB) was not "
                f"authorized. Set {OPT_IN_VARIABLE}=1 to allow the download on first use, or use the offline "
                f"'hashing' embedder."
            )
        self._function = None  # created lazily: the model is only touched when text is embedded

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._function is None:
            from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

            function = ONNXMiniLM_L6_V2()
            function.DOWNLOAD_PATH = self._model_dir  # type: ignore[misc]
            self._function = function
        return [[float(x) for x in vector] for vector in self._function(texts)]


# --- selection by name -------------------------------------------------------------------------

EMBEDDERS = ("hashing", "minilm")


def default_embedder_name() -> str:
    return os.environ.get("EMBEDDER", "minilm")


def embedder_by_name(name: str | None = None) -> Embedder:
    name = name or default_embedder_name()
    if name == "hashing":
        return HashingEmbedder()
    if name == "minilm":
        return MiniLMEmbedder()
    raise ValueError(f"Unknown embedder {name!r}. Valid embedders: {', '.join(EMBEDDERS)}")
