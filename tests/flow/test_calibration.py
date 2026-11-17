"""Spec: retrieval results below a minimum score count as no evidence; the defaults are calibrated on measured data.

Measured 2026-11-17 (best passage score per question, 22 relevant / 8 off-topic / 4 absent-but-in-domain):
  hashing      relevant 0.13-0.54 (median 0.33)   off-topic 0.06-0.30   absent 0.09-0.27   -> default 0.15
  minilm-l6-v2 relevant 0.34-0.72 (median 0.54)   off-topic 0.09-0.18   absent 0.17-0.34   -> default 0.30
Absent-but-in-domain questions reach the scores of relevant ones (0.32-0.34 with MiniLM): no threshold separates
them, so the answer stage has to say what is missing. They are measured here but not asserted.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ecosystem_assistant.knowledge.flow.graph import DEFAULT_MIN_SCORES, default_min_score
from ecosystem_assistant.knowledge.retrieval.embedders import MiniLMEmbedder, model_is_cached
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from tests.data.helpers import SAMPLE

RELEVANT = [q["question"] for q in yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "evaluation" / "retrieval.yaml").read_text(encoding="utf-8"))["questions"]]
OFF_TOPIC = [
    "What is the capital of France?", "How do I bake sourdough bread at home?",
    "Who won the football world cup in 2018?", "What will the weather be like tomorrow in Madrid?",
    "Explain quantum entanglement in simple words.", "How tall is Mount Everest?",
    "Recommend a good science fiction novel.", "How do I change a flat tire on my bicycle?",
]


def best_score(index: RetrievalIndex, question: str) -> float:
    return max((hit.score for hit in index.search(question, k=5)), default=0.0)


def rates(index: RetrievalIndex, min_score: float) -> tuple[float, float]:
    kept = sum(best_score(index, q) >= min_score for q in RELEVANT) / len(RELEVANT)
    rejected = sum(best_score(index, q) < min_score for q in OFF_TOPIC) / len(OFF_TOPIC)
    return kept, rejected


def test_every_known_embedder_has_a_default() -> None:
    assert set(DEFAULT_MIN_SCORES) == {"hashing", "minilm-l6-v2"}
    assert all(0.0 < default_min_score(name) < 1.0 for name in DEFAULT_MIN_SCORES)


def test_the_offline_default_keeps_relevant_questions_and_rejects_off_topic_ones(sample_index: RetrievalIndex) -> None:
    kept, rejected = rates(sample_index, default_min_score("hashing"))
    assert kept >= 0.9, f"the default drops too many relevant questions ({kept:.2f} kept)"
    assert rejected >= 0.85, f"the default lets off-topic questions through ({rejected:.2f} rejected)"


def test_the_minilm_default_keeps_relevant_questions_and_rejects_off_topic_ones(tmp_path: Path) -> None:
    if not model_is_cached():
        pytest.skip("the MiniLM model is not cached; nothing is downloaded by the tests")
    index = RetrievalIndex(tmp_path / "index", MiniLMEmbedder())
    index.sync(SAMPLE)

    kept, rejected = rates(index, default_min_score("minilm-l6-v2"))

    assert kept >= 0.9, f"the default drops too many relevant questions ({kept:.2f} kept)"
    assert rejected >= 0.85, f"the default lets off-topic questions through ({rejected:.2f} rejected)"
