"""Spec: the live check makes real calls only with an explicit opt-in, and says what it costs first."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from ecosystem_assistant.llm.anthropic_chat import anthropic_chat_model
from ecosystem_assistant.llm.anthropic_llm import AnthropicLLM
from ecosystem_assistant.llm.ledger import Ledger
from tests.llm.test_anthropic_chat import Wire, build, message
from tests.llm.test_anthropic_llm import FakeClient, reply

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "live_check.py"


def load_script():
    spec = importlib.util.spec_from_file_location("live_check", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["live_check"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def parts(tmp_path: Path):
    ledger = Ledger(tmp_path / "ledger.json", cap_usd=1.0)
    client = FakeClient(reply('{"answer": "hello"}', 120, 15))
    wire = Wire(message("ok", input_tokens=20, output_tokens=4),
                message(None, {"name": "ping", "input": {"x": "hi"}}, input_tokens=90, output_tokens=25))
    return ledger, client, wire, AnthropicLLM(client=client, ledger=ledger), build(wire, ledger)


@pytest.mark.parametrize(("env", "argv"), [
    ({}, []),                          # neither
    ({"LIVE_LLM": "1"}, []),           # the variable without the confirmation flag
    ({"LIVE_LLM": "0"}, ["--yes"]),    # the flag with the variable switched off
])
def test_without_both_opt_ins_nothing_is_called_and_it_says_what_to_set(env, argv, parts, capsys) -> None:
    ledger, client, wire, llm, chat = parts

    code = load_script().main(argv, env=env, llm=llm, chat=chat)

    out = capsys.readouterr().out
    assert code == 2 and "LIVE_LLM=1" in out and "--yes" in out
    assert client.requests == [] and wire.requests == [] and ledger.total().calls == 0


def test_the_flag_alone_is_not_enough(parts, capsys) -> None:
    _l, client, wire, llm, chat = parts
    assert load_script().main(["--yes"], env={}, llm=llm, chat=chat) == 2
    assert client.requests == [] and wire.requests == []


def test_with_both_it_prints_the_estimate_first_then_calls_and_reports_what_was_spent(parts, capsys) -> None:
    ledger, client, wire, llm, chat = parts

    code = load_script().main(["--yes"], env={"LIVE_LLM": "1"}, llm=llm, chat=chat)

    lines = capsys.readouterr().out.splitlines()
    assert code == 0
    estimate = next(i for i, line in enumerate(lines) if "estimated cost" in line.lower())
    first_result = next(i for i, line in enumerate(lines) if line.startswith(("flow:", "agent:")))
    assert estimate < first_result  # the person is told before anything is spent
    assert len(client.requests) == 1 and len(wire.requests) == 2
    text = "\n".join(lines)
    assert "tokens used: 230 in, 44 out" in text  # 120+20+90 in, 15+4+25 out
    assert "ledger total" in text.lower() and "cap" in text.lower()
    assert ledger.total().calls == 3


def test_it_reports_a_failed_check_with_a_nonzero_exit(tmp_path: Path, capsys) -> None:
    ledger = Ledger(tmp_path / "l.json", cap_usd=1.0)
    llm = AnthropicLLM(client=FakeClient(reply("not json")), ledger=ledger)
    chat = build(Wire(message("ok")), ledger)

    code = load_script().main(["--yes"], env={"LIVE_LLM": "1"}, llm=llm, chat=chat)

    assert code == 1 and "FAIL" in capsys.readouterr().out
