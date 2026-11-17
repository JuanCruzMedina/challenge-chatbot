"""Spec: the review set is graded by the effect on the files, with right and wrong scripted reviews."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import yaml

from ecosystem_assistant.agent.scripted_chat import ScriptedChat, ai_text, ai_tool
from ecosystem_assistant.llm.scripted import ScriptedLLM
from tests.agent.test_knowledge_service import oracle
from tests.data.helpers import SAMPLE

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "eval_pr_review.py"
REAL_SET = Path(__file__).resolve().parents[2] / "evaluation" / "pr_review.yaml"
QUOTED = "v1 does **not** support automatic retries: after a failure, the consumer must create a new charge."


def load_script():
    spec = importlib.util.spec_from_file_location("eval_pr_review", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_pr_review"] = module
    spec.loader.exec_module(module)
    return module


def right_script() -> list[Any]:
    return [
        ai_tool("add_document", {"service": "orders-service", "doc_path": "docs/coupons.md",
                                 "content": "# Coupons\n\nA customer applies one coupon per order.\n"}),
        ai_text("Added a document about coupons."),
        ai_tool("update_document", {"service": "payments-service", "doc_path": "docs/api-v1.md", "old_text": QUOTED,
                                    "new_text": "v1 now retries a failed charge up to 3 times automatically."}),
        ai_text("Updated the retries rule."),
        *[ai_text("No documentation change is needed.") for _ in range(4)],
    ]


def run_main(script: list[Any], capsys, extra: list[str] | None = None) -> tuple[int, str]:
    module = load_script()
    code = module.main(["--min-score", "0.0", *(extra or [])], chat=ScriptedChat(script=script),
                       flow_llm=ScriptedLLM(responder=oracle()))
    return code, capsys.readouterr().out


def test_the_real_set_is_well_formed_and_not_vacuous() -> None:
    cases = yaml.safe_load(REAL_SET.read_text(encoding="utf-8"))["cases"]
    module = load_script()
    assert len(cases) == 6 and {c["kind"] for c in cases} == {"new", "update", "unchanged"}
    assert len({c["id"] for c in cases}) == 6
    for case in cases:
        service = case["pr"]["repo"].rsplit("/", 1)[-1]
        if case["kind"] == "update":
            text = (Path(SAMPLE) / case["expect"]["path"]).read_text(encoding="utf-8")
            assert module._contains(text, case["expect"]["removed"]), "the statement to replace must exist today"
            assert not any(module._contains(text, p) for p in case["expect"]["added_any"])
        if case["kind"] == "new":
            sample_docs = "\n".join(p.read_text(encoding="utf-8") for p in (Path(SAMPLE) / "repos" / service).rglob("*.md"))
            assert not any(module._contains(sample_docs, p) for p in case["expect"]["new_mentions"])


def test_right_reviews_pass_and_the_report_groups_by_kind(capsys) -> None:
    code, out = run_main(right_script(), capsys, ["--min-rate", "1.0"])

    assert code == 0, out
    assert "Pass rate: 6/6 = 1.00" in out
    assert "By kind: new 1/1, update 1/1, unchanged 4/4" in out


def test_wrong_reviews_fail_with_the_reason(capsys) -> None:
    wrong = [
        ai_text("Nothing to document."),                                   # r01 new: nothing created
        ai_text("Nothing to update."),                                     # r02 update: nothing changed
        ai_tool("add_document", {"service": "orders-service", "doc_path": "docs/refactor-notes.md",
                                 "content": "# Refactor\n\nHelpers were renamed.\n"}),
        ai_text("Documented the refactor."),                               # r03 unchanged: wrote anyway
        *[ai_text("Nothing.") for _ in range(3)],
    ]

    code, out = run_main(wrong, capsys, ["--min-rate", "0.9"])

    assert code == 1
    assert "no new markdown file was created" in out
    assert "still says" in out
    assert "changed documentation that did not need it" in out
    assert "By kind: new 0/1, update 0/1, unchanged 3/4" in out


def test_an_unusable_model_aborts_with_code_2(capsys) -> None:
    from ecosystem_assistant.agent.settings import AgentModelError

    code, out = run_main([AgentModelError("Cannot reach the model. Start it with `ollama serve`.")], capsys)

    assert code == 2 and "ABORTED" in out and "ollama serve" in out
