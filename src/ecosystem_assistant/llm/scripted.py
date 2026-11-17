"""A scripted model for tests and demos: replays responses, records every call (design.md D-2)."""
from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ecosystem_assistant.llm.port import LLMError, LLMOutputError


class ScriptExhaustedError(LLMError):
    """The script has no response left for this call."""


@dataclass(frozen=True)
class Call:
    kind: str                       # "complete" or "json"
    system: str
    user: str
    schema: dict[str, Any] | None


class ScriptedLLM:
    """Answers from a list of responses (text, a dict, or an exception to raise) or from a function."""

    name = "scripted"

    def __init__(self, responses: Sequence[Any] | None = None,
                 responder: Callable[[Call], Any] | None = None) -> None:
        self._responses = list(responses or [])
        self._responder = responder
        self.calls: list[Call] = []

    def _next(self, call: Call) -> Any:
        self.calls.append(call)
        if self._responder is not None:
            response = self._responder(call)
        elif self._responses:
            response = self._responses.pop(0)
        else:
            raise ScriptExhaustedError(
                f"The scripted model ran out of responses at call {len(self.calls)} ({call.kind})."
            )
        if isinstance(response, Exception):
            raise response
        return response

    def complete(self, system: str, user: str) -> str:
        response = self._next(Call("complete", system, user, None))
        return response if isinstance(response, str) else json.dumps(response)

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        response = self._next(Call("json", system, user, schema))
        return parse_json_object(response)


def parse_json_object(response: Any) -> dict[str, Any]:
    """A dict stays as it is; text must parse to a JSON object. Anything else is an output error."""
    if isinstance(response, dict):
        return response
    if not isinstance(response, str):
        raise LLMOutputError(f"Expected a JSON object, got {type(response).__name__}.")
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError as exc:
        raise LLMOutputError(f"The model did not return valid JSON ({exc.msg}): {response[:80]!r}") from exc
    if not isinstance(parsed, dict):
        raise LLMOutputError(f"Expected a JSON object, got {type(parsed).__name__}: {response[:80]!r}")
    return parsed
