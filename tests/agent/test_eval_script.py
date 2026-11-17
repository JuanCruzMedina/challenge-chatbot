"""Spec: the routing evaluation reports per turn and overall, fails an action on a question, and isolates turns."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from ecosystem_assistant.agent.records import AgentReply, ToolCallRecord
from ecosystem_assistant.knowledge.flow.catalog import PLAN_SCHEMA
from ecosystem_assistant.llm.scripted import Call, ScriptedLLM
from tests.agent.fake_chat import ScriptedChat, ai_text, ai_tool
from tests.data.helpers import SAMPLE

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "eval_agent.py"
REAL_SET = Path(__file__).resolve().parents[2] / "evaluation" / "agent.yaml"
ADD = {"service": "notifications-service", "doc_path": "docs/eval-note.md", "content": "# Note\n\nfresh note text\n"}


def load_script():
    spec = importlib.util.spec_from_file_location("eval_agent", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_agent"] = module
    spec.loader.exec_module(module)
    return module


def record(name: str, error: bool = False, arguments: dict | None = None, result: str = "ok") -> ToolCallRecord:
    return ToolCallRecord(name, arguments or {}, result, error)


# --- grading rules (no model involved) ---------------------------------------------------------------

def grade(turn: dict[str, Any], text: str, calls: list[ToolCallRecord], workspace: Path | None = None,
          baseline: Path | None = None, audit: Path | None = None):
    module = load_script()
    return module.grade(turn, AgentReply(text, calls), workspace or Path("/nonexistent"),
                        baseline or Path("/nonexistent"), audit or Path("/nonexistent/audit.jsonl"))


QUESTION = {"id": "q", "kind": "question", "message": "m", "expect_tools": ["query_knowledge"], "expect_facts": ["Alpha"]}


def test_a_question_answered_with_the_knowledge_tool_and_the_facts_passes(tmp_path: Path) -> None:
    assert grade(QUESTION, "It is ALPHA.", [record("query_knowledge")], tmp_path, tmp_path).passed


def test_an_action_tool_called_on_a_question_fails_and_names_the_tool(tmp_path: Path) -> None:
    verdict = grade(QUESTION, "Alpha", [record("query_knowledge"), record("add_document")], tmp_path, tmp_path)
    assert not verdict.passed
    assert any("add_document" in r and "question" in r for r in verdict.reasons)


@pytest.mark.parametrize(("calls", "word"), [
    ([], "not called"),                                              # the expected tool never ran
    ([record("query_knowledge", error=True)], "never succeeded"),    # it ran but always failed
    ([record("query_knowledge"), record("some_other_tool")], "some_other_tool"),
])
def test_missing_failed_and_unexpected_tools_fail_the_turn(calls: list[ToolCallRecord], word: str, tmp_path: Path) -> None:
    verdict = grade(QUESTION, "Alpha", calls, tmp_path, tmp_path)
    assert not verdict.passed and any(word in r for r in verdict.reasons)


def test_a_missing_fact_in_the_reply_fails_the_turn(tmp_path: Path) -> None:
    verdict = grade(QUESTION, "No idea.", [record("query_knowledge")], tmp_path, tmp_path)
    assert not verdict.passed and any("Alpha" in r for r in verdict.reasons)


def test_tools_must_be_first_called_in_the_expected_order(tmp_path: Path) -> None:
    mixed = {"id": "m", "kind": "mixed", "message": "m", "expect_tools": ["query_knowledge", "add_document"],
             "expect_effect": {"path": "x.md", "contains": ["y"]}}
    (tmp_path / "x.md").write_text("y", encoding="utf-8")
    base = tmp_path / "base"
    base.mkdir()
    wrong = grade(mixed, "ok", [record("add_document"), record("query_knowledge")], tmp_path, base)
    right = grade(mixed, "ok", [record("query_knowledge"), record("add_document")], tmp_path, base)
    assert any("order" in r for r in wrong.reasons) and right.passed


def test_the_allowed_extra_tools_are_not_penalized(tmp_path: Path) -> None:
    unsupported = {"id": "u", "kind": "unsupported", "message": "m", "expect_tools": [], "allow_tools": ["query_knowledge"]}
    assert grade(unsupported, "I cannot do that.", [record("query_knowledge")], tmp_path, tmp_path).passed


def test_a_turn_with_no_expected_effect_must_leave_the_workspace_untouched(tmp_path: Path) -> None:
    workspace, baseline = tmp_path / "ws", tmp_path / "base"
    for folder in (workspace, baseline):
        folder.mkdir()
        (folder / "a.md").write_text("same", encoding="utf-8")
    chat = {"id": "c", "kind": "chat", "message": "hi", "expect_tools": []}

    assert grade(chat, "Hello!", [], workspace, baseline).passed
    (workspace / "a.md").write_text("changed", encoding="utf-8")
    verdict = grade(chat, "Hello!", [], workspace, baseline)
    assert not verdict.passed and any("changed the workspace" in r for r in verdict.reasons)


def test_an_effect_must_be_in_the_file_and_the_absent_text_must_be_gone(tmp_path: Path) -> None:
    workspace, baseline = tmp_path / "ws", tmp_path / "base"
    workspace.mkdir()
    baseline.mkdir()
    (baseline / "d.md").write_text("old text here", encoding="utf-8")
    action = {"id": "a", "kind": "action", "message": "m", "expect_tools": ["update_document"],
              "expect_effect": {"path": "d.md", "contains": ["new text"], "absent": ["old text"]}}
    calls = [record("update_document")]

    (workspace / "d.md").write_text("new text here", encoding="utf-8")
    assert grade(action, "done", calls, workspace, baseline).passed
    (workspace / "d.md").write_text("new text and old text", encoding="utf-8")
    assert any("old text" in r for r in grade(action, "done", calls, workspace, baseline).reasons)
    (workspace / "d.md").unlink()
    assert any("does not exist" in r for r in grade(action, "done", calls, workspace, baseline).reasons)


def test_an_effect_that_was_already_in_the_file_before_the_turn_invalidates_the_turn(tmp_path: Path) -> None:
    workspace, baseline = tmp_path / "ws", tmp_path / "base"
    for folder in (workspace, baseline):
        folder.mkdir()
        (folder / "d.md").write_text("status: obsolete already", encoding="utf-8")
    action = {"id": "a", "kind": "action", "message": "m", "expect_tools": ["mark_document_obsolete"],
              "expect_effect": {"path": "d.md", "contains": ["status: obsolete"]}}

    verdict = grade(action, "done", [record("mark_document_obsolete")], workspace, baseline)

    assert not verdict.passed and any("already" in r for r in verdict.reasons)


# --- the script end to end with a scripted chat model ------------------------------------------------------

def oracle_chat(plans: dict[str, list[AIMessage]]) -> ScriptedChat:
    """A chat model that follows a plan per user message: the n-th model call of a turn gives the n-th message."""
    def respond(messages: list) -> AIMessage:
        last_human = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        used = sum(isinstance(m, ToolMessage) for m in messages[last_human:])
        return plans[messages[last_human].content][used]
    return ScriptedChat(responder=respond)


def flow_llm() -> ScriptedLLM:
    def respond(call: Call) -> Any:
        if call.schema == PLAN_SCHEMA:
            return {"graph_queries": [{"method": "service_owner", "arguments": {"service": "tracking-service"}}]}
        return {"answer": "tracking-team owns it and Bruno Salas leads it [K1]", "citations": ["K1"]}
    return ScriptedLLM(responder=respond)


TURNS = [
    {"id": "t1", "kind": "question", "message": "who owns tracking", "expect_tools": ["query_knowledge"],
     "expect_facts": ["tracking-team"]},
    {"id": "t2", "kind": "action", "message": "write the note", "expect_tools": ["add_document"],
     "expect_effect": {"path": "repos/notifications-service/docs/eval-note.md", "contains": ["fresh note text"]}},
    {"id": "t3", "kind": "question", "message": "a question that wrongly writes", "expect_tools": ["query_knowledge"]},
    {"id": "t4", "kind": "chat", "message": "hello", "expect_tools": []},
    {"id": "t5", "kind": "action", "message": "write the note again", "expect_tools": ["add_document"],
     "expect_effect": {"path": "repos/notifications-service/docs/eval-note.md", "contains": ["fresh note text"]}},
]
PLANS = {
    "who owns tracking": [ai_tool("query_knowledge", {"question": "who owns tracking"}),
                          ai_text("tracking-team owns it [K1].")],
    "write the note": [ai_tool("add_document", ADD), ai_text("Done.")],
    "a question that wrongly writes": [ai_tool("add_document", ADD), ai_text("Done.")],
    "hello": [ai_text("Hello!")],
    "write the note again": [ai_tool("add_document", ADD), ai_text("Done.")],
}


def write_set(tmp_path: Path, turns: list[dict]) -> Path:
    path = tmp_path / "turns.yaml"
    path.write_text(yaml.safe_dump({"turns": turns}), encoding="utf-8")
    return path


def run_script(tmp_path: Path, capsys: pytest.CaptureFixture[str], turns: list[dict], plans: dict, *extra: str):
    code = load_script().main(["--questions", str(write_set(tmp_path, turns)), "--embedder", "hashing", *extra],
                              chat=oracle_chat(plans), flow_llm=flow_llm())
    return code, capsys.readouterr().out.splitlines()


def test_the_report_has_one_line_per_turn_and_an_overall_rate(tmp_path, capsys) -> None:
    code, lines = run_script(tmp_path, capsys, TURNS, PLANS)

    by_id = {line.split()[0]: line for line in lines if line.split() and line.split()[0] in {t["id"] for t in TURNS}}
    assert "PASS" in by_id["t1"] and "PASS" in by_id["t2"] and "FAIL" in by_id["t3"] and "PASS" in by_id["t4"]
    assert "query_knowledge" in by_id["t1"] and "add_document" in by_id["t2"]
    assert any("add_document" in line and "reasons" in line for line in lines)  # why t3 failed
    assert any(line.startswith("Pass rate: 4/5 = 0.80") for line in lines)
    assert code == 0


def test_turns_do_not_see_each_others_effects(tmp_path, capsys) -> None:
    """t2 and t5 create the same file. If the workspace were shared, the second add would fail with 'already exists'."""
    _code, lines = run_script(tmp_path, capsys, TURNS, PLANS)
    t5 = next(line for line in lines if line.startswith("t5"))
    assert "PASS" in t5


def test_a_rate_below_the_minimum_fails_the_run(tmp_path, capsys) -> None:
    assert run_script(tmp_path, capsys, TURNS, PLANS, "--min-rate", "0.7")[0] == 0
    code, lines = run_script(tmp_path, capsys, TURNS, PLANS, "--min-rate", "0.95")
    assert code == 1 and any("below the minimum" in line for line in lines)


def test_the_project_workspace_and_data_are_never_touched(tmp_path, capsys) -> None:
    before = sorted(p.relative_to(SAMPLE).as_posix() for p in SAMPLE.rglob("*") if p.is_file())
    run_script(tmp_path, capsys, TURNS, PLANS)
    assert sorted(p.relative_to(SAMPLE).as_posix() for p in SAMPLE.rglob("*") if p.is_file()) == before


def test_the_real_set_runs_with_a_clueless_model_and_gives_a_report_not_a_crash(tmp_path, capsys) -> None:
    code = load_script().main(["--questions", str(REAL_SET), "--embedder", "hashing"],
                              chat=ScriptedChat(responder=lambda messages: ai_text("I do not know.")), flow_llm=flow_llm())
    lines = capsys.readouterr().out.splitlines()
    total = len(yaml.safe_load(REAL_SET.read_text(encoding="utf-8"))["turns"])
    assert code == 0 and any(line.startswith("Pass rate:") for line in lines)
    assert sum(1 for line in lines if line.split() and line.split()[0][0] in "qamcu" and line.split()[1:2] and
               line.split()[1] in {"PASS", "FAIL"}) == total
