"""Ollama adapter of the model port (design.md D-2).

ollama 0.6 client API, confirmed with a throwaway probe (task 1.2):
- ``ollama.Client(host=..., **httpx_kwargs)``; the timeout goes in the keyword arguments
  (``Client(host, timeout=120)``) and is handed to httpx.
- ``client.chat(model=, messages=[{"role": ..., "content": ...}], format=<JSON schema dict>,
  options={"temperature": 0})`` returns a response whose ``message.content`` is the text.
- With no server running it raises the builtin ``ConnectionError`` ("Failed to connect to Ollama...").
- Other errors: ``ollama.ResponseError`` (the server answered with an error, for example a model that
  is not pulled) and ``ollama.RequestError``.
"""
from __future__ import annotations

from typing import Any

import httpx
import ollama

from ecosystem_assistant.llm.port import LLMError, LLMOutputError, LLMUnavailableError
from ecosystem_assistant.llm.scripted import parse_json_object
from ecosystem_assistant.llm.settings import OllamaSettings, ollama_settings_from_env


class OllamaLLM:
    """A local model served by Ollama. Temperature is always zero; nothing leaves the machine."""

    def __init__(self, settings: OllamaSettings | None = None, client: Any | None = None) -> None:
        self.settings = settings or ollama_settings_from_env()
        self.name = f"ollama:{self.settings.model}"
        self._client = client if client is not None else ollama.Client(
            host=self.settings.host, timeout=self.settings.timeout
        )

    def complete(self, system: str, user: str) -> str:
        return self._chat(system, user, None)

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        try:
            return parse_json_object(self._chat(system, user, schema))
        except LLMOutputError as exc:
            raise LLMOutputError(f"{self.name}: {exc}") from exc

    def _chat(self, system: str, user: str, schema: dict[str, Any] | None) -> str:
        s = self.settings
        try:
            response = self._client.chat(
                model=s.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                format=schema,
                options={"temperature": 0},
            )
        except (ConnectionError, TimeoutError, httpx.HTTPError) as exc:
            raise LLMUnavailableError(
                f"Cannot reach Ollama at {s.host} ({exc}). Start it with `ollama serve`, "
                f"and make sure the model is available with `ollama pull {s.model}`."
            ) from exc
        except ollama.ResponseError as exc:
            if getattr(exc, "status_code", None) == 404:
                raise LLMUnavailableError(
                    f"Ollama at {s.host} does not have the model {s.model!r}. Pull it with `ollama pull {s.model}`."
                ) from exc
            raise LLMError(f"Ollama at {s.host} returned an error: {exc}") from exc
        return response["message"]["content"] or ""
