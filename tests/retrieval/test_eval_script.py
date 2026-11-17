"""Spec: the evaluation reports per question and overall, and fails below the minimum hit rate."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

from tests.data.helpers import SAMPLE
from tests.retrieval.helpers import populate

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "eval_retrieval.py"
REAL_SET = Path(__file__).resolve().parents[2] / "evaluation" / "retrieval.yaml"


def load_script():
    spec = importlib.util.spec_from_file_location("eval_retrieval", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_retrieval"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def small_case(fx_root: Path, tmp_path: Path) -> tuple[Path, Path]:
    """A tiny dataset and an evaluation set with one question that can be found and one that cannot."""
    populate(fx_root)
    questions = tmp_path / "questions.yaml"
    questions.write_text(yaml.safe_dump({"questions": [
        {"id": "hit-1", "question": "How many widgets are allowed on each page?",
         "expected": ["repos/svc-a1/docs/api.md"]},
        # The expected document does not exist, so this question can never be a hit (no chance involved).
        {"id": "miss-1", "question": "Where does the quantum banana ferment on tuesdays?",
         "expected": ["repos/svc-nowhere/README.md"]},
    ]}), encoding="utf-8")
    return fx_root, questions


def run(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, list[str]]:
    code = load_script().main(args)
    return code, capsys.readouterr().out.splitlines()


def test_the_report_has_one_line_per_question_and_an_overall_rate(
    small_case: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    root, questions = small_case

    code, lines = run(["--root", str(root), "--questions", str(questions), "--embedder", "hashing", "--k", "3"], capsys)

    assert code == 0
    hit = next(line for line in lines if line.startswith("hit-1"))
    miss = next(line for line in lines if line.startswith("miss-1"))
    assert "HIT" in hit and "rank 1" in hit
    assert "MISS" in miss and "rank" not in miss.replace("MISS", "")
    overall = [line for line in lines if line.startswith("Hit rate")]
    assert overall == ["Hit rate @3: 1/2 = 0.50 (embedder: hashing)"]


def test_a_hit_rate_below_the_minimum_fails_the_run(
    small_case: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    root, questions = small_case
    args = ["--root", str(root), "--questions", str(questions), "--embedder", "hashing"]

    assert run([*args, "--min-hit-rate", "0.5"], capsys)[0] == 0
    code, lines = run([*args, "--min-hit-rate", "0.9"], capsys)

    assert code == 1
    assert any("below the minimum" in line for line in lines)


def test_the_evaluation_never_touches_the_project_index(
    small_case: tuple[Path, Path], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root, questions = small_case
    monkeypatch.setenv("VECTOR_INDEX_DIR", str(tmp_path / "must-stay-empty"))

    run(["--root", str(root), "--questions", str(questions), "--embedder", "hashing"], capsys)

    assert not (tmp_path / "must-stay-empty").exists()  # it uses a throwaway index of its own


def test_the_offline_embedder_keeps_a_reasonable_hit_rate_on_the_real_set() -> None:
    """A regression floor, not a quality claim: measured 0.86 (19/22) when the set was written."""
    results = load_script().evaluate(SAMPLE, REAL_SET, "hashing", k=3)
    rate = sum(r.hit for r in results) / len(results)
    assert rate >= 0.7, f"the offline embedder dropped to {rate:.2f}"


def test_the_real_evaluation_set_runs_end_to_end_with_the_offline_embedder(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, lines = run(["--root", str(SAMPLE), "--questions", str(REAL_SET), "--embedder", "hashing"], capsys)

    questions = yaml.safe_load(REAL_SET.read_text(encoding="utf-8"))["questions"]
    assert code == 0
    assert sum(1 for line in lines if line.startswith("q")) == len(questions)
    assert any(line.startswith("Hit rate") for line in lines)
