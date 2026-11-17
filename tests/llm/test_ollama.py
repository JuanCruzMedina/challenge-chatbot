"""Spec: the Ollama adapter uses temperature zero, the schema as format, and reports an unreachable server."""
from __future__ import annotations

from typing import Any

import ollama
import pytest

from ecosystem_assistant.llm.ollama_llm import OllamaLLM
from ecosystem_assistant.llm.port import LLMError, LLMOutputError, LLMUnavailableError
from ecosystem_assistant.llm.settings import OllamaSettings

SETTINGS = OllamaSettings(host="http://127.0.0.1:11434", model="test-model:1b", timeout=7.5)
SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}


class FakeClient:
    """Stands in for ollama.Client: records what it was asked and answers with canned content or an error."""

    def __init__(self, content: str = "", error: Exception | None = None) -> None:
        self.content, self.error, self.calls = content, error, []

    def chat(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"message": {"role": "assistant", "content": self.content}}


def test_a_text_call_sends_the_prompts_with_temperature_zero_and_no_format() -> None:
    client = FakeClient("hello there")
    answer = OllamaLLM(SETTINGS, client=client).complete("be brief", "say hi")

    sent = client.calls[0]
    assert answer == "hello there"
    assert sent["model"] == "test-model:1b"
    assert sent["messages"] == [{"role": "system", "content": "be brief"}, {"role": "user", "content": "say hi"}]
    assert sent["options"] == {"temperature": 0}
    assert sent.get("format") is None


def test_a_json_call_passes_the_schema_as_format_and_parses_the_answer() -> None:
    client = FakeClient('{"answer": "42"}')
    result = OllamaLLM(SETTINGS, client=client).complete_json("sys", "usr", SCHEMA)

    assert result == {"answer": "42"}
    assert client.calls[0]["format"] == SCHEMA
    assert client.calls[0]["options"] == {"temperature": 0}


@pytest.mark.parametrize("content", ["not json", "", "[1, 2]", '"text"'])
def test_content_that_is_not_a_json_object_is_an_output_error(content: str) -> None:
    with pytest.raises(LLMOutputError):
        OllamaLLM(SETTINGS, client=FakeClient(content)).complete_json("sys", "usr", SCHEMA)


def test_the_default_client_is_built_with_the_host_and_the_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, Any] = {}

    class Recording(FakeClient):
        def __init__(self, host: str | None = None, **kwargs: Any) -> None:
            super().__init__("ok")
            created.update(host=host, **kwargs)

    monkeypatch.setattr(ollama, "Client", Recording)
    OllamaLLM(SETTINGS).complete("s", "u")

    assert created == {"host": "http://127.0.0.1:11434", "timeout": 7.5}


def test_an_unreachable_server_says_the_address_and_how_to_start_it() -> None:
    client = FakeClient(error=ConnectionError("Failed to connect to Ollama."))
    with pytest.raises(LLMUnavailableError) as exc:
        OllamaLLM(SETTINGS, client=client).complete("s", "u")

    message = str(exc.value)
    assert "http://127.0.0.1:11434" in message and "ollama serve" in message


def test_a_timeout_is_reported_as_an_unavailable_model() -> None:
    with pytest.raises(LLMUnavailableError, match="ollama serve"):
        OllamaLLM(SETTINGS, client=FakeClient(error=TimeoutError("timed out"))).complete_json("s", "u", SCHEMA)


def test_a_model_that_is_not_pulled_says_which_one_to_pull() -> None:
    client = FakeClient(error=ollama.ResponseError("model 'test-model:1b' not found", 404))
    with pytest.raises(LLMUnavailableError) as exc:
        OllamaLLM(SETTINGS, client=client).complete("s", "u")
    assert "ollama pull test-model:1b" in str(exc.value)


def test_another_server_error_is_a_plain_model_error() -> None:
    client = FakeClient(error=ollama.ResponseError("internal failure", 500))
    with pytest.raises(LLMError) as exc:
        OllamaLLM(SETTINGS, client=client).complete("s", "u")
    assert not isinstance(exc.value, LLMUnavailableError)
    assert "internal failure" in str(exc.value)


def test_the_name_carries_the_model() -> None:
    assert OllamaLLM(SETTINGS, client=FakeClient()).name == "ollama:test-model:1b"
