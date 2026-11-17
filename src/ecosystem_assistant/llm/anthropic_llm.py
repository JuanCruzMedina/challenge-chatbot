"""Anthropic adapter of the model port (design.md D-2).

Facts confirmed with a throwaway probe against anthropic 2.9.0 and ``claude-haiku-5-5`` (task 1.2):
- ``client.messages.create(model=, max_tokens=, system=, messages=[...], output_config={"effort": "low"})`` returns
  text blocks whose joined text is the answer.
- ``output_config.format`` (structured outputs) works for closed schemas but the API rejects any object that does not
  set ``additionalProperties: false`` (found by a real call: HTTP 400). The flow's plan schema has a free-form map of
  arguments, which that mode cannot express, so JSON is requested in the instructions instead (the schema is appended
  to the system prompt), the reply may arrive in a code fence, and the flow validates it and retries on its own.
- ``temperature`` is not a parameter of ``messages.create`` in this SDK (sampling parameters are gone): never pass it.
- With ``effort: "low"`` no thinking blocks come back and a short reply costs a handful of output tokens.
- ``response.usage`` has ``input_tokens`` and ``output_tokens`` (output includes thinking tokens, billed as output).
- Errors: ``AuthenticationError`` (401), ``PermissionDeniedError``, ``RateLimitError``, ``InternalServerError``
  (also used for 529 overloaded) are ``APIStatusError``; ``APIConnectionError`` (with ``APITimeoutError`` below it).
- With no key set, or an empty ``ANTHROPIC_API_KEY``, ``anthropic.Anthropic()`` authenticates with the
  ``ant auth login`` session (checked offline: the request carries a Bearer token).
- The SDK uses ``httpx2``, not ``httpx``: a test transport must come from ``httpx2``.
"""
from __future__ import annotations

import json
import re
from typing import Any

import anthropic

from ecosystem_assistant.llm.anthropic_errors import explain_anthropic_error
from ecosystem_assistant.llm.ledger import Ledger
from ecosystem_assistant.llm.port import LLMError, LLMOutputError, LLMUnavailableError
from ecosystem_assistant.llm.pricing import model_from_env
from ecosystem_assistant.llm.scripted import parse_json_object

MAX_TOKENS = 1500   # bounds the output (and so the cost) of every flow call
TIMEOUT_SECONDS = 120.0
EFFORT = "low"      # D9: low effort to save reasoning tokens


FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _unfence(text: str) -> str:
    """The model sometimes wraps JSON in a code fence; that is not part of the JSON."""
    stripped = text.strip()
    match = FENCE.match(stripped)
    return match.group(1) if match else stripped


class AnthropicLLM:
    """Claude through the Anthropic API. Every call is checked against and recorded in the spending ledger."""

    def __init__(self, model: str | None = None, client: Any | None = None, ledger: Ledger | None = None) -> None:
        self.model = model_from_env({"ANTHROPIC_MODEL": model} if model else None)
        self.name = f"anthropic:{self.model}"
        self.ledger = ledger or Ledger.from_env()
        self._client = client if client is not None else anthropic.Anthropic(timeout=TIMEOUT_SECONDS)

    def complete(self, system: str, user: str) -> str:
        return self._call(system, user, None)

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        try:
            return parse_json_object(_unfence(self._call(system, user, schema)))
        except LLMOutputError as exc:
            raise LLMOutputError(f"{self.name}: {exc}") from exc

    def _call(self, system: str, user: str, schema: dict[str, Any] | None) -> str:
        self.ledger.check()  # refuses before anything is sent once the cap is reached
        if schema is not None:
            system = (f"{system}\n\nReply with only one JSON object that follows this JSON Schema, with no other "
                      f"text and no code fence:\n{json.dumps(schema)}")
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": EFFORT},
            )
        except anthropic.APIError as exc:
            message = explain_anthropic_error(exc, self.model)
            if message is None:
                raise
            raise LLMUnavailableError(message) from exc
        self.ledger.record(self.model, response.usage.input_tokens, response.usage.output_tokens)
        if response.stop_reason == "refusal":
            raise LLMError(f"{self.name} declined to answer this request.")
        text = "".join(block.text for block in response.content if block.type == "text")
        if response.stop_reason == "max_tokens" and schema is not None:
            raise LLMOutputError(f"the answer was cut off at max_tokens={MAX_TOKENS} before the JSON was complete")
        return text
