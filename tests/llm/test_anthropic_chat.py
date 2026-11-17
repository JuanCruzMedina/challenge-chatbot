"""Spec: the agent's Anthropic chat model uses the login session, the ledger and the price table (no network)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anthropic
import httpx2
import pytest
from langchain_core.tools import tool

from ecosystem_assistant.llm.anthropic_chat import SessionChatAnthropic, anthropic_chat_model
from ecosystem_assistant.llm.ledger import BudgetExceededError, Ledger
from ecosystem_assistant.llm.pricing import UnknownModelError

MODEL = "claude-haiku-5-5"


def message(text: str | None = "ok", tool_use: dict[str, Any] | None = None, input_tokens: int = 10,
            output_tokens: int = 5) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    if text is not None:
        content.append({"type": "text", "text": text})
    if tool_use is not None:
        content.append({"type": "tool_use", "id": "toolu_1", **tool_use})
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": MODEL, "content": content,
            "stop_reason": "tool_use" if tool_use else "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}}


class Wire:
    """A fake Anthropic API: records the requests it receives and answers with the next body or status."""

    def __init__(self, *responses: Any) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content))
        item = self.responses.pop(0)
        if isinstance(item, int):
            return httpx2.Response(item, json={"type": "error", "error": {"type": "error", "message": "boom"}})
        return httpx2.Response(200, json=item)


def build(wire: Wire, ledger: Ledger, **kwargs: Any) -> SessionChatAnthropic:
    chat = anthropic_chat_model(ledger=ledger, max_retries=0, **kwargs)
    chat.__dict__["_client"] = anthropic.Anthropic(
        api_key="test", max_retries=0, http_client=httpx2.Client(transport=httpx2.MockTransport(wire)))
    chat.__dict__["_async_client"] = anthropic.AsyncAnthropic(
        api_key="test", max_retries=0, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(wire)))
    return chat


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    return Ledger(tmp_path / "ledger.json", cap_usd=1.0)


@tool
def ping(x: str) -> str:
    """Ping."""
    return x


# --- authentication ------------------------------------------------------------------------------------

def test_an_empty_key_is_not_sent_so_the_sdk_resolves_the_session() -> None:
    assert "api_key" not in SessionChatAnthropic(model=MODEL, anthropic_api_key="")._client_params


def test_a_key_with_a_value_is_kept() -> None:
    assert SessionChatAnthropic(model=MODEL, anthropic_api_key="sk-ant-test")._client_params["api_key"] == "sk-ant-test"


def test_an_unset_key_variable_is_also_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert "api_key" not in SessionChatAnthropic(model=MODEL)._client_params


# --- the model and its requests --------------------------------------------------------------------------

def test_the_default_model_is_the_cheap_one_and_a_model_without_a_price_is_refused(ledger: Ledger) -> None:
    assert anthropic_chat_model(ledger=ledger).model == MODEL
    with pytest.raises(UnknownModelError, match="claude-opus-5-5"):
        anthropic_chat_model(model="claude-opus-5-5", ledger=ledger)


def test_the_request_has_low_effort_and_no_sampling_parameters(ledger: Ledger) -> None:
    wire = Wire(message("hello"))

    reply = build(wire, ledger).invoke("hi")

    assert reply.content == "hello"
    request = wire.requests[0]
    assert request["model"] == MODEL and request["output_config"] == {"effort": "low"}
    assert "temperature" not in request and "top_p" not in request and "top_k" not in request


def test_a_tool_call_comes_back_through_bind_tools(ledger: Ledger) -> None:
    wire = Wire(message(None, {"name": "ping", "input": {"x": "hi"}}))

    reply = build(wire, ledger).bind_tools([ping]).invoke("call ping")

    assert reply.tool_calls[0]["name"] == "ping" and reply.tool_calls[0]["args"] == {"x": "hi"}
    assert wire.requests[0]["tools"][0]["name"] == "ping"


# --- the ledger ----------------------------------------------------------------------------------------

def test_usage_is_recorded_after_each_call_sync_and_async(ledger: Ledger) -> None:
    import asyncio

    wire = Wire(message("a", input_tokens=100, output_tokens=20), message("b", input_tokens=50, output_tokens=10))
    chat = build(wire, ledger)

    chat.invoke("one")
    asyncio.run(chat.ainvoke("two"))

    total = ledger.total()
    assert (total.calls, total.input_tokens, total.output_tokens) == (2, 150, 30)


def test_a_call_after_the_cap_is_refused_before_any_request(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "l.json", cap_usd=0.0005)
    ledger.record(MODEL, 0, 1_000)
    wire = Wire(message("never"))

    with pytest.raises(BudgetExceededError, match="cap"):
        build(wire, ledger).invoke("hi")

    assert wire.requests == []


def test_the_cap_also_stops_the_async_path(tmp_path: Path) -> None:
    import asyncio

    ledger = Ledger(tmp_path / "l.json", cap_usd=0.0005)
    ledger.record(MODEL, 0, 1_000)
    wire = Wire(message("never"))

    with pytest.raises(BudgetExceededError):
        asyncio.run(build(wire, ledger).ainvoke("hi"))
    assert wire.requests == []


def test_a_failed_call_records_nothing(ledger: Ledger) -> None:
    with pytest.raises(anthropic.RateLimitError):
        build(Wire(429), ledger).invoke("hi")
    assert ledger.total().calls == 0
