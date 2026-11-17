"""Spec: every evaluation question points at a real document."""
from __future__ import annotations

from pathlib import Path

import yaml

from ecosystem_assistant.knowledge.retrieval.documents import discover_documents
from tests.data.helpers import SAMPLE

EVAL_SET = Path(__file__).resolve().parents[2] / "evaluation" / "retrieval.yaml"


def _questions() -> list[dict]:
    return yaml.safe_load(EVAL_SET.read_text(encoding="utf-8"))["questions"]


def test_every_expected_document_exists_and_is_indexable() -> None:
    indexable = set(discover_documents(SAMPLE))
    for question in _questions():
        assert question["expected"], question["id"]
        for path in question["expected"]:
            assert (SAMPLE / path).is_file(), f"{question['id']}: {path} does not exist"
            assert path in indexable, f"{question['id']}: {path} would not be indexed"


def test_the_set_is_well_formed() -> None:
    questions = _questions()
    ids = [q["id"] for q in questions]
    assert len(questions) >= 15
    assert len(ids) == len(set(ids))
    assert all(q["question"].strip().endswith(("?", ".")) and len(q["question"]) > 20 for q in questions)


def test_the_questions_cover_every_kind_of_document() -> None:
    expected = {p for q in _questions() for p in q["expected"]}
    assert any("runbook" in p for p in expected)
    assert any("/api" in p for p in expected)
    assert any("adr-" in p for p in expected)
    assert any(p.startswith("clients/") for p in expected)
    assert any(p.startswith("company/") for p in expected)
    assert any(p.endswith("README.md") for p in expected)
    # Both clients are represented: their product visions and services of each.
    assert "clients/demo-grocery/product/vision.md" in expected
    assert "clients/demo-logistics/product/vision.md" in expected
    grocery = {"catalog-service", "orders-service", "payments-service", "notifications-service"}
    logistics = {"tracking-service", "routing-service", "driver-service"}
    assert any(p.split("/")[1] in grocery for p in expected if p.startswith("repos/"))
    assert any(p.split("/")[1] in logistics for p in expected if p.startswith("repos/"))
