"""Spec: the Anthropic adapter of the model port, with a fake client (no network, no cost)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from ecosystem_assistant.llm.anthropic_llm import AnthropicLLM
from ecosystem_assistant.llm.ledger import BudgetExceededError, Ledger
from ecosystem_assistant.llm.port import LLMError, LLMOutputError, LLMUnavailableError
from ecosystem_assistant.llm.pricing import UnknownModelError

SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"],
          "additionalProperties": False}


def reply(text: str, input_tokens: int = 100, output_tokens: int = 20, stop: str = "end_turn") -> Any:
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop,
                           usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens))


class FakeClient:
    """Stands in for anthropic.Anthropic: records each request and returns (or raises) the next outcome."""

    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def api_error(cls: type, status: int) -> Exception:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("boom", response=httpx2.Response(status, request=request), body=None)


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    return Ledger(tmp_path / "ledger.json", cap_usd=1.0)


def llm(client: FakeClient, ledger: Ledger) -> AnthropicLLM:
    return AnthropicLLM(client=client, ledger=ledger)


# --- the port ------------------------------------------------------------------------------------------

def test_complete_sends_the_prompts_and_returns_the_text(ledger: Ledger) -> None:
    client = FakeClient(reply("hello there"))

    text = llm(client, ledger).complete("be brief", "say hello")

    assert text == "hello there"
    request = client.requests[0]
    assert request["model"] == "claude-haiku-5-5" and request["system"] == "be brief"
    assert request["messages"] == [{"role": "user", "content": "say hello"}]
    assert request["output_config"] == {"effort": "low"}
    assert "temperature" not in request and request["max_tokens"] > 0


def test_complete_json_asks_for_the_schema_and_returns_the_object(ledger: Ledger) -> None:
    client = FakeClient(reply('{"answer": "42"}'))

    result = llm(client, ledger).complete_json("sys", "user", SCHEMA)

    assert result == {"answer": "42"}
    assert client.requests[0]["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}


def test_invalid_json_is_an_output_error_that_names_the_model(ledger: Ledger) -> None:
    with pytest.raises(LLMOutputError, match="anthropic:claude-haiku-5-5"):
        llm(FakeClient(reply("not json at all")), ledger).complete_json("s", "u", SCHEMA)


def test_a_json_answer_cut_off_by_the_token_limit_is_an_output_error(ledger: Ledger) -> None:
    with pytest.raises(LLMOutputError, match="max_tokens"):
        llm(FakeClient(reply('{"answer": "cut', stop="max_tokens")), ledger).complete_json("s", "u", SCHEMA)


def test_a_refusal_is_a_model_error_not_an_empty_answer(ledger: Ledger) -> None:
    with pytest.raises(LLMError, match="declined"):
        llm(FakeClient(reply("", stop="refusal")), ledger).complete("s", "u")


def test_the_name_identifies_provider_and_model(ledger: Ledger) -> None:
    assert llm(FakeClient(), ledger).name == "anthropic:claude-haiku-5-5"


def test_a_model_without_a_price_is_refused_at_creation(ledger: Ledger) -> None:
    with pytest.raises(UnknownModelError, match="claude-opus-5-5"):
        AnthropicLLM(model="claude-opus-5-5", client=FakeClient(), ledger=ledger)


# --- the ledger ----------------------------------------------------------------------------------------

def test_every_call_is_recorded_with_its_usage(ledger: Ledger) -> None:
    adapter = llm(FakeClient(reply("a", 100, 20), reply('{"answer": "b"}', 300, 40)), ledger)

    adapter.complete("s", "u")
    adapter.complete_json("s", "u", SCHEMA)

    total = ledger.total()
    assert (total.calls, total.input_tokens, total.output_tokens) == (2, 400, 60)


def test_the_call_after_the_cap_is_refused_before_it_is_sent(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "l.json", cap_usd=0.0005)
    ledger.record("claude-haiku-5-5", 0, 1_000)  # exactly the cap
    client = FakeClient(reply("never used"))

    with pytest.raises(BudgetExceededError, match="cap"):
        llm(client, ledger).complete("s", "u")

    assert client.requests == []  # nothing was sent


def test_a_failed_call_records_nothing(ledger: Ledger) -> None:
    with pytest.raises(LLMUnavailableError):
        llm(FakeClient(api_error(anthropic.RateLimitError, 429)), ledger).complete("s", "u")
    assert ledger.total().calls == 0


# --- failures --------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("error", "advice"), [
    (api_error(anthropic.AuthenticationError, 401), "ant auth login"),
    (api_error(anthropic.PermissionDeniedError, 403), "ANTHROPIC_API_KEY"),
    (api_error(anthropic.RateLimitError, 429), "wait"),
    (api_error(anthropic.InternalServerError, 529), "overloaded"),
    (api_error(anthropic.NotFoundError, 404), "claude-haiku-5-5"),
    (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com")), "connection"),
    (anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com")), "connection"),
])
def test_each_service_failure_says_what_to_do(error: Exception, advice: str, ledger: Ledger) -> None:
    with pytest.raises(LLMUnavailableError) as exc:
        llm(FakeClient(error), ledger).complete("s", "u")
    assert advice.lower() in str(exc.value).lower()


def test_an_unexpected_exception_is_not_disguised(ledger: Ledger) -> None:
    with pytest.raises(ZeroDivisionError):
        llm(FakeClient(ZeroDivisionError("bug")), ledger).complete("s", "u")


def test_a_bad_request_is_a_bug_and_is_not_disguised(ledger: Ledger) -> None:
    with pytest.raises(anthropic.BadRequestError):
        llm(FakeClient(api_error(anthropic.BadRequestError, 400)), ledger).complete("s", "u")


def test_creating_the_adapter_makes_no_network_call(ledger: Ledger, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9")
    adapter = AnthropicLLM(ledger=ledger)  # builds the real client; connecting would fail loudly
    assert adapter.name == "anthropic:claude-haiku-5-5"


def test_missing_credentials_name_both_ways_to_authenticate(ledger: Ledger) -> None:
    with pytest.raises(LLMUnavailableError) as exc:
        llm(FakeClient(api_error(anthropic.AuthenticationError, 401)), ledger).complete("s", "u")
    assert "ANTHROPIC_API_KEY" in str(exc.value) and "ant auth login" in str(exc.value)


def test_a_flow_call_and_an_agent_call_add_up_in_one_ledger(ledger: Ledger) -> None:
    from tests.llm.test_anthropic_chat import Wire, build, message

    flow = llm(FakeClient(reply('{"answer": "a"}', 300, 40)), ledger)
    agent = build(Wire(message("ok", input_tokens=700, output_tokens=60)), ledger)

    flow.complete_json("s", "u", SCHEMA)
    agent.invoke("hi")

    total = ledger.total()
    assert (total.calls, total.input_tokens, total.output_tokens) == (2, 1_000, 100)
    assert total.cost_usd == pytest.approx(1_000 * 0.10 / 1e6 + 100 * 0.50 / 1e6)
