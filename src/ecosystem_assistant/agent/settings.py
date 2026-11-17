"""The agent's chat model and how its failures are reported (design.md D-2).

It reads the same ``OLLAMA_*`` settings as the informational flow, so one configuration drives both.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping

import httpx
import ollama
from langchain_ollama import ChatOllama

from ecosystem_assistant.llm.settings import OllamaSettings, ollama_settings_from_env


class AgentModelError(RuntimeError):
    """The agent's model cannot be used. The message says what to do; no other model is tried."""


def chat_model_from_env(env: Mapping[str, str] | None = None) -> ChatOllama:
    """The local model that decides which tool to call. Temperature is zero; nothing leaves the machine."""
    settings = ollama_settings_from_env(os.environ if env is None else env)
    return ChatOllama(
        model=settings.model,
        base_url=settings.host,
        temperature=0,
        client_kwargs={"timeout": settings.timeout},
    )


def translate_model_error(settings: OllamaSettings | None = None) -> Callable[[Exception], Exception]:
    """Turn the failures that mean "this model server cannot be used" into :class:`AgentModelError`.

    Every other exception is returned as it is: a bug must not be disguised as a model problem.
    """
    s = settings or ollama_settings_from_env()

    def translate(exc: Exception) -> Exception:
        if isinstance(exc, (httpx.HTTPError, ConnectionError, TimeoutError)):
            return AgentModelError(
                f"Cannot reach the model server at {s.host} ({exc}). Start it with `ollama serve`, and make sure the "
                f"model is available with `ollama pull {s.model}`."
            )
        if isinstance(exc, ollama.ResponseError):
            status = getattr(exc, "status_code", None)
            if status == 404:
                return AgentModelError(
                    f"The model server at {s.host} does not have the model {s.model!r}. Pull it with "
                    f"`ollama pull {s.model}`."
                )
            if "tool" in str(exc).lower():
                return AgentModelError(
                    f"The model {s.model!r} cannot call tools, which the agent needs. Set OLLAMA_MODEL to a model "
                    f"that supports tool calling (for example qwen2.5:7b-instruct)."
                )
        return exc

    return translate
