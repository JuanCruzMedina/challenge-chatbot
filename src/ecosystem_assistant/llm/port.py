"""The model port: the only thing the rest of the project knows about a language model (design.md D-1)."""
from __future__ import annotations

from typing import Any, Protocol


class LLMError(Exception):
    """A language model failed to do what was asked."""


class LLMUnavailableError(LLMError):
    """The model cannot be reached or does not exist. The message says how to fix it."""


class LLMOutputError(LLMError):
    """The model answered, but not with what was asked for (for example invalid JSON)."""


class LLM(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str:
        """Free text for a system prompt and a user prompt."""
        ...

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        """A JSON object that follows ``schema``. Raises :class:`LLMOutputError` when it cannot be parsed."""
        ...
