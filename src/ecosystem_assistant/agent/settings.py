"""The agent's chat model and how its failures are reported (design.md D-2).

It reads the same ``OLLAMA_*`` settings as the informational flow, so one configuration drives both.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Mapping

import httpx
import ollama
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama

from ecosystem_assistant.llm.anthropic_errors import explain_anthropic_error
from ecosystem_assistant.llm.ledger import BudgetExceededError
from ecosystem_assistant.llm.pricing import DEFAULT_MODEL
from ecosystem_assistant.llm.settings import AGENT_PROVIDERS, OllamaSettings, ollama_settings_from_env


class AgentModelError(RuntimeError):
    """The agent's model cannot be used. The message says what to do; no other model is tried."""


def chat_model_from_env(env: Mapping[str, str] | None = None) -> BaseChatModel:
    """The model that decides which tool to call, chosen by ``LLM_PROVIDER`` (default ``ollama``, local and free).

    Creating it never connects anywhere. With ``anthropic`` every call is checked against the spending ledger.
    """
    env = os.environ if env is None else env
    provider = env.get("LLM_PROVIDER") or "ollama"
    if provider == "anthropic":
        from ecosystem_assistant.llm.anthropic_chat import anthropic_chat_model
        from ecosystem_assistant.llm.ledger import Ledger

        return anthropic_chat_model(model=env.get("ANTHROPIC_MODEL") or None, ledger=Ledger.from_env(env))
    if provider != "ollama":
        raise ValueError(
            f"Unknown LLM_PROVIDER {provider!r} for the agent. Valid providers for the agent: "
            f"{', '.join(AGENT_PROVIDERS)}"
        )
    settings = ollama_settings_from_env(env)
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
        if isinstance(exc, BudgetExceededError):  # the Anthropic spending cap: its message says how to change it
            return AgentModelError(str(exc))
        anthropic_message = explain_anthropic_error(exc, os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL)
        if anthropic_message is not None:
            return AgentModelError(anthropic_message)
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
