"""Which model to use and where it lives, from the environment (design.md D-2)."""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from ecosystem_assistant.llm.port import LLM

PROVIDERS = ("ollama", "fake")
DEFAULT_PROVIDER = "ollama"
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_TIMEOUT = 120.0


@dataclass(frozen=True)
class OllamaSettings:
    host: str = DEFAULT_HOST
    model: str = DEFAULT_MODEL
    timeout: float = DEFAULT_TIMEOUT


def ollama_settings_from_env(env: Mapping[str, str] | None = None) -> OllamaSettings:
    env = os.environ if env is None else env
    raw_timeout = env.get("OLLAMA_TIMEOUT")
    try:
        timeout = float(raw_timeout) if raw_timeout else DEFAULT_TIMEOUT
    except ValueError as exc:
        raise ValueError(f"OLLAMA_TIMEOUT must be a number of seconds, got {raw_timeout!r}") from exc
    return OllamaSettings(
        host=env.get("OLLAMA_HOST") or DEFAULT_HOST,
        model=env.get("OLLAMA_MODEL") or DEFAULT_MODEL,
        timeout=timeout,
    )


def llm_from_env(env: Mapping[str, str] | None = None) -> LLM:
    """The model chosen by ``LLM_PROVIDER`` (default ``ollama``). Creating it never connects anywhere."""
    env = os.environ if env is None else env
    provider = env.get("LLM_PROVIDER") or DEFAULT_PROVIDER
    if provider == "ollama":
        from ecosystem_assistant.llm.ollama_llm import OllamaLLM

        return OllamaLLM(ollama_settings_from_env(env))
    if provider == "fake":
        from ecosystem_assistant.llm.scripted import ScriptedLLM

        return ScriptedLLM()
    raise ValueError(f"Unknown LLM_PROVIDER {provider!r}. Valid providers: {', '.join(PROVIDERS)}")
