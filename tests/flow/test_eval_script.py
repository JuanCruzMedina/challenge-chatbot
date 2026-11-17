"""Spec: the flow evaluation reports per question and overall, grades without a judge, and fails below the minimum."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from ecosystem_assistant.knowledge.flow.answer import Answer, Citation
from ecosystem_assistant.knowledge.flow.catalog import PLAN_SCHEMA
from ecosystem_assistant.llm.scripted import Call, ScriptedLLM
from tests.data.helpers import SAMPLE

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "eval_flow.py"
OWNER = "Who owns the tracking service and who leads it?"
LIMIT = "How many requests per minute may a consumer make to the tracking API?"
CAPITAL = "What is the capital of France?"


def load_script():
    spec = importlib.util.spec_from_file_location("eval_flow", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_flow"] = module
    spec.loader.exec_module(module)
    return module


def answer(status: str = "answered", grounded: bool = True, text: str = "", sources: list[str] | None = None) -> Answer:
    citations = [Citation("K1", "graph", "x", sources or [])]
    return Answer("q", text, status, grounded, citations, [])


# --- grading rules (no model involved) ----------------------------------------------------------------

GRADED = {"id": "g", "kind": "graph", "question": "q", "expect_sources": ["a.yaml", "b.md"], "expect_facts": ["Alpha", "42"]}


def test_a_grounded_answer_with_the_sources_and_every_fact_passes() -> None:
    grade = load_script().grade
    verdict = grade({**GRADED, "source_mode": "all"}, answer(text="ALPHA is 42.", sources=["a.yaml", "b.md"]))
    assert verdict.passed and verdict.reasons == []


@pytest.mark.parametrize(("given", "mode", "passes"), [
    (["a.yaml"], "any", True), (["b.md"], "any", True), ([], "any", False),
    (["a.yaml"], "all", False), (["a.yaml", "b.md"], "all", True), (["other.md"], "any", False),
])
def test_the_source_mode_decides_how_many_expected_sources_must_be_cited(given: list[str], mode: str, passes: bool) -> None:
    verdict = load_script().grade({**GRADED, "source_mode": mode}, answer(text="alpha 42", sources=given))
    assert verdict.passed is passes
    assert passes or any("source" in r for r in verdict.reasons)


@pytest.mark.parametrize(("fact", "text", "found"), [
    ("fleet-tracker", "The Fleet Tracker application", True),       # an id written as its display name
    ("driver-app", "Driver App and Fleet Tracker", True),
    ("tracking-team", "owned by TRACKING_TEAM", True),
    ("Bruno Salas", "led by bruno   salas.", True),
    ("20", "it takes 20 seconds", True),
    ("20", "up to 200 requests", False),                            # whole words only, not substrings
    ("200", "2000 requests", False),
    ("fleet-tracker", "the fleet and the tracker", False),          # the words must be adjacent and in order
])
def test_a_fact_matches_by_whole_words_ignoring_case_and_separators(fact: str, text: str, found: bool) -> None:
    item = {"id": "g", "kind": "graph", "question": "q", "expect_sources": ["a.yaml"], "expect_facts": [fact]}
    verdict = load_script().grade(item, answer(text=text, sources=["a.yaml"]))
    assert verdict.passed is found


def test_a_missing_fact_fails_and_names_the_fact() -> None:
    verdict = load_script().grade(GRADED, answer(text="Alpha only", sources=["a.yaml"]))
    assert not verdict.passed and any("42" in r for r in verdict.reasons)


@pytest.mark.parametrize(("status", "grounded", "word"), [("degraded", True, "degraded"),
                                                          ("answered", False, "grounded"),
                                                          ("insufficient_evidence", False, "evidence")])
def test_the_status_and_the_grounding_must_be_right(status: str, grounded: bool, word: str) -> None:
    verdict = load_script().grade(GRADED, answer(status, grounded, "alpha 42", ["a.yaml"]))
    assert not verdict.passed and any(word in r for r in verdict.reasons)


def test_an_unknown_question_passes_only_with_insufficient_evidence() -> None:
    grade = load_script().grade
    item = {"id": "u", "kind": "unknown", "question": "q"}
    assert grade(item, answer("insufficient_evidence", False, "I could not find information")).passed
    assert not grade(item, answer("answered", True, "Paris", ["a.yaml"])).passed


def test_an_absent_question_passes_with_insufficient_evidence_or_an_answer_that_says_it_is_missing() -> None:
    grade = load_script().grade
    item = {"id": "a", "kind": "absent", "question": "q"}
    assert grade(item, answer("insufficient_evidence", False, "nothing found")).passed
    assert grade(item, answer("answered", True, "The documentation does not mention who the CEO is.")).passed
    assert grade(item, answer("answered", True, "There is no information about a CEO in the evidence.")).passed
    assert not grade(item, answer("answered", True, "The CEO is Ana Lopez [D1].")).passed


# --- the script end to end with a scripted oracle ----------------------------------------------------

def oracle(wrong_fact_for: str | None = None):
    """Plans and answers like a good model would for the three questions below; wrong on purpose for one."""
    def respond(call: Call) -> Any:
        question = re.search(r"Question: (.*)", call.user).group(1).strip()
        if call.schema == PLAN_SCHEMA:
            if question == OWNER:
                return {"graph_queries": [{"method": "service_owner", "arguments": {"service": "tracking-service"}}]}
            return {"graph_queries": []}
        cited = re.findall(r"\[((?:K|D)\d+)\]", call.user.split("EVIDENCE", 1)[1])
        text = {OWNER: "tracking-team owns it and Bruno Salas leads it.", LIMIT: "Up to 300 requests per minute."}[question]
        if question == wrong_fact_for:
            text = "It is somebody else's business."
        return {"answer": text + " " + " ".join(f"[{c}]" for c in dict.fromkeys(cited)), "citations": list(dict.fromkeys(cited))}
    return respond


def write_set(tmp_path: Path, questions: list[dict]) -> Path:
    path = tmp_path / "questions.yaml"
    path.write_text(yaml.safe_dump({"questions": questions}), encoding="utf-8")
    return path


GRAPH_Q = {"id": "t1", "kind": "graph", "question": OWNER, "expect_sources": ["repos/tracking-service/service.yaml"],
           "expect_facts": ["tracking-team", "Bruno Salas"]}
DOC_Q = {"id": "t2", "kind": "document", "question": LIMIT,
         "expect_sources": ["repos/tracking-service/docs/api.md"], "expect_facts": ["300"]}


def run(tmp_path: Path, capsys: pytest.CaptureFixture[str], questions: list[dict], llm: ScriptedLLM,
        *extra: str) -> tuple[int, list[str]]:
    code = load_script().main(["--root", str(SAMPLE), "--questions", str(write_set(tmp_path, questions)),
                               "--embedder", "hashing", *extra], llm=llm)
    return code, capsys.readouterr().out.splitlines()


def test_the_report_has_a_line_per_question_and_an_overall_rate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, lines = run(tmp_path, capsys, [GRAPH_Q, DOC_Q], ScriptedLLM(responder=oracle(wrong_fact_for=LIMIT)))

    first = next(line for line in lines if line.startswith("t1"))
    second = next(line for line in lines if line.startswith("t2"))
    assert "PASS" in first and "graph" in first
    assert "FAIL" in second and "document" in second
    assert any("300" in line and "reasons" in line for line in lines)
    assert any(line.startswith("Pass rate: 1/2 = 0.50") for line in lines)
    assert code == 0


def test_a_rate_below_the_minimum_fails_the_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    llm = lambda: ScriptedLLM(responder=oracle(wrong_fact_for=LIMIT))  # noqa: E731
    assert run(tmp_path, capsys, [GRAPH_Q, DOC_Q], llm(), "--min-rate", "0.5")[0] == 0
    code, lines = run(tmp_path, capsys, [GRAPH_Q, DOC_Q], llm(), "--min-rate", "0.9")
    assert code == 1 and any("below the minimum" in line for line in lines)


def test_an_unknown_question_passes_when_nothing_reaches_the_minimum_score(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    item = {"id": "t3", "kind": "unknown", "question": CAPITAL}
    code, lines = run(tmp_path, capsys, [item], ScriptedLLM(responder=oracle()), "--min-score", "1.01")
    assert code == 0 and any(line.startswith("t3") and "PASS" in line for line in lines)


def test_the_whole_real_set_runs_with_a_scripted_model_without_crashing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Mechanics only: a model that always plans nothing and answers badly must give a report, not an error."""
    def clueless(call: Call) -> Any:
        if call.schema == PLAN_SCHEMA:
            return {"graph_queries": []}
        return {"answer": "I do not know.", "citations": []}

    real = Path(__file__).resolve().parents[2] / "evaluation" / "flow.yaml"
    code = load_script().main(["--root", str(SAMPLE), "--questions", str(real), "--embedder", "hashing"],
                              llm=ScriptedLLM(responder=clueless))
    lines = capsys.readouterr().out.splitlines()
    total = len(yaml.safe_load(real.read_text(encoding="utf-8"))["questions"])
    assert code == 0 and sum(1 for line in lines if re.match(r"f\d\d ", line)) == total
    assert any(line.startswith("Pass rate:") for line in lines)
