"""The agent's Anthropic chat model (design.md D-3). It lives in ``llm`` so that only this package imports the SDK.

Facts confirmed with a throwaway probe against langchain-anthropic 1.7.10 / anthropic 2.9.0 (task 1.2):
- ``ChatAnthropic`` passes ``api_key=SecretStr('')`` when no key is set, so the SDK sends ``Bearer `` and fails;
  dropping an empty ``api_key`` in ``_client_params`` lets the SDK use the ``ant auth login`` session.
- ``output_config`` is an explicit field: ``ChatAnthropic(output_config={"effort": "low"})`` reaches the request
  payload. ``temperature`` stays ``None`` and is not sent (Haiku 5.5 rejects non-default sampling values).
- ``AIMessage.usage_metadata`` carries ``input_tokens``, ``output_tokens`` and ``total_tokens``.
- ``bind_tools`` and tool calls work through the subclass, synchronously and asynchronously.
"""
from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import BaseCallbackHandler

from ecosystem_assistant.llm.ledger import Ledger
from ecosystem_assistant.llm.pricing import model_from_env

MAX_TOKENS = 2048   # bounds the output (and so the cost) of one agent step
EFFORT = "low"      # D9: low effort to save reasoning tokens


class SessionChatAnthropic(ChatAnthropic):
    """``ChatAnthropic`` that works with the ``ant auth login`` session when no API key is set."""

    @property
    def _client_params(self) -> dict[str, Any]:
        params = super()._client_params
        if not params.get("api_key"):
            params.pop("api_key", None)  # an empty key would make the SDK send ``Bearer `` and fail
        return params


class LedgerCallback(BaseCallbackHandler):
    """Refuses a call once the cap is reached, and records the usage of every call that finishes."""

    raise_error = True   # a refusal must stop the call, not be logged and ignored
    run_inline = True

    def __init__(self, ledger: Ledger, model: str) -> None:
        self.ledger = ledger
        self.model = model

    def on_chat_model_start(self, serialized: dict[str, Any], messages: Any, **kwargs: Any) -> None:
        self.ledger.check()

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        for generations in response.generations:
            for generation in generations:
                usage = getattr(getattr(generation, "message", None), "usage_metadata", None)
                if usage:
                    self.ledger.record(self.model, usage["input_tokens"], usage["output_tokens"])


def anthropic_chat_model(
    model: str | None = None, ledger: Ledger | None = None, **options: Any
) -> SessionChatAnthropic:
    """The agent's model: low effort, a bounded output and every call checked against the spending ledger."""
    name = model_from_env({"ANTHROPIC_MODEL": model} if model else None)
    guard = LedgerCallback(ledger or Ledger.from_env(), name)
    return SessionChatAnthropic(
        model=name, max_tokens=MAX_TOKENS, output_config={"effort": EFFORT}, callbacks=[guard], **options
    )
