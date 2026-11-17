"""Spec: every flow evaluation question points at real sources and facts that exist in the data."""
from __future__ import annotations

from pathlib import Path

import yaml

from ecosystem_assistant.knowledge.graph.build import build_graph
from tests.data.helpers import SAMPLE

EVAL_SET = Path(__file__).resolve().parents[2] / "evaluation" / "flow.yaml"
KINDS = {"graph", "document", "combined", "unknown", "absent"}
GRADED = {"graph", "document", "combined"}


def _questions() -> list[dict]:
    return yaml.safe_load(EVAL_SET.read_text(encoding="utf-8"))["questions"]


def test_the_set_is_well_formed_and_covers_every_kind() -> None:
    questions = _questions()
    ids = [q["id"] for q in questions]
    assert len(questions) >= 12 and len(ids) == len(set(ids))
    assert {q["kind"] for q in questions} == KINDS
    assert all(q["question"].strip().endswith("?") for q in questions)
    assert all(q.get("source_mode", "any") in {"any", "all"} for q in questions)


def test_every_graded_question_names_sources_and_facts_and_the_others_name_none() -> None:
    for q in _questions():
        if q["kind"] in GRADED:
            assert q["expect_sources"] and q["expect_facts"], q["id"]
        else:
            assert "expect_sources" not in q and "expect_facts" not in q, q["id"]


def test_every_expected_source_exists_under_the_data_root() -> None:
    for q in _questions():
        for path in q.get("expect_sources", []):
            assert (SAMPLE / path).is_file(), f"{q['id']}: {path} does not exist"


def test_every_expected_fact_really_appears_in_the_data() -> None:
    corpus = "\n".join(p.read_text(encoding="utf-8").lower() for p in SAMPLE.rglob("*") if p.suffix in {".md", ".yaml"})
    for q in _questions():
        for fact in q.get("expect_facts", []):
            assert fact.lower() in corpus, f"{q['id']}: the fact {fact!r} is not in the data"


def test_the_graph_knows_the_entities_the_graph_questions_are_about() -> None:
    graph = build_graph(SAMPLE)
    for name in ("payments-api", "tracking-service", "payment.failed", "demo-logistics", "driver-service",
                 "catalog-api"):
        assert graph.find_entities(name), name
