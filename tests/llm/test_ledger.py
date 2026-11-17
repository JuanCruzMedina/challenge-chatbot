"""Spec: a persistent ledger adds up every call and refuses the next one once the cap is reached."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from ecosystem_assistant.llm.ledger import BudgetExceededError, Ledger, cap_from_env
from ecosystem_assistant.llm.port import LLMUnavailableError

MODEL = "claude-haiku-5-5"


def test_calls_add_up_across_instances_sharing_one_file(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    flow, agent = Ledger(path, cap_usd=1.0), Ledger(path, cap_usd=1.0)

    flow.record(MODEL, 1_000, 200)
    agent.record(MODEL, 2_000, 300)

    total = Ledger(path, cap_usd=1.0).total()
    assert (total.input_tokens, total.output_tokens, total.calls) == (3_000, 500, 2)
    assert total.cost_usd == pytest.approx(3_000 * 0.10 / 1e6 + 500 * 0.50 / 1e6)


def test_the_total_survives_a_new_process_reading_the_file(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    Ledger(path, cap_usd=1.0).record(MODEL, 5_000, 1_000)

    assert json.loads(path.read_text(encoding="utf-8"))["calls"] == 1
    assert Ledger(path, cap_usd=1.0).total().input_tokens == 5_000


def test_check_passes_below_the_cap_and_raises_exactly_when_the_cap_is_reached(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "l.json", cap_usd=0.0005)  # 1000 output tokens cost 0.0005
    ledger.check()  # nothing spent

    ledger.record(MODEL, 0, 999)
    ledger.check()  # 0.0004995: below the cap

    ledger.record(MODEL, 0, 1)  # now exactly the cap
    with pytest.raises(BudgetExceededError) as exc:
        ledger.check()
    message = str(exc.value)
    assert "0.0005" in message and "ANTHROPIC_MAX_USD" in message  # the total/cap and how to change it


def test_the_budget_error_is_a_model_unavailable_error(tmp_path: Path) -> None:
    assert issubclass(BudgetExceededError, LLMUnavailableError)


def test_a_missing_ledger_file_is_an_empty_ledger_and_is_created_on_the_first_record(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "ledger.json"
    ledger = Ledger(path, cap_usd=1.0)
    assert ledger.total().calls == 0 and not path.exists()

    ledger.record(MODEL, 10, 10)

    assert path.is_file()


def test_a_corrupt_ledger_stops_the_calls_instead_of_resetting_the_total(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(BudgetExceededError, match="ledger"):
        Ledger(path, cap_usd=1.0).check()
    assert path.read_text(encoding="utf-8") == "{not json"  # left for the user to look at


def test_the_file_is_replaced_atomically_and_leaves_no_temporary_files(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.json", cap_usd=1.0)
    for _ in range(5):
        ledger.record(MODEL, 100, 10)

    assert sorted(p.name for p in tmp_path.iterdir()) == ["ledger.json", "ledger.json.lock"]


def test_concurrent_records_do_not_lose_updates(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"

    def work() -> None:
        ledger = Ledger(path, cap_usd=100.0)
        for _ in range(25):
            ledger.record(MODEL, 10, 1)

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total = Ledger(path, cap_usd=100.0).total()
    assert (total.calls, total.input_tokens, total.output_tokens) == (200, 2_000, 200)


def test_a_model_without_a_price_cannot_be_recorded(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="claude-opus-5-5"):
        Ledger(tmp_path / "l.json", cap_usd=1.0).record("claude-opus-5-5", 1, 1)


# --- configuration -------------------------------------------------------------------------------------

def test_the_cap_defaults_to_one_dollar_and_can_be_set() -> None:
    assert cap_from_env({}) == 1.0
    assert cap_from_env({"ANTHROPIC_MAX_USD": "2.5"}) == 2.5
    assert cap_from_env({"ANTHROPIC_MAX_USD": ""}) == 1.0


@pytest.mark.parametrize("bad", ["abc", "-1", "0", "nan", "inf"])
def test_an_invalid_cap_fails_naming_the_variable(bad: str) -> None:
    with pytest.raises(ValueError, match="ANTHROPIC_MAX_USD"):
        cap_from_env({"ANTHROPIC_MAX_USD": bad})


def test_from_env_uses_the_configured_path_and_cap(tmp_path: Path) -> None:
    ledger = Ledger.from_env({"ANTHROPIC_LEDGER": str(tmp_path / "x.json"), "ANTHROPIC_MAX_USD": "3"})
    assert ledger.path == tmp_path / "x.json" and ledger.cap_usd == 3.0
    assert Ledger.from_env({}).path == Path(".cost_ledger.json")
