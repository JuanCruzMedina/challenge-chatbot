"""Spec: the provider is chosen by configuration, and the Ollama settings come from the environment."""
from __future__ import annotations

import pytest

from ecosystem_assistant.llm.ollama_llm import OllamaLLM
from ecosystem_assistant.llm.scripted import ScriptedLLM
from ecosystem_assistant.llm.settings import PROVIDERS, llm_from_env, ollama_settings_from_env


def test_ollama_settings_have_local_defaults() -> None:
    settings = ollama_settings_from_env({})
    assert settings.host == "http://localhost:11434"
    assert settings.model == "qwen2.5:7b-instruct"
    assert settings.timeout == 120.0


def test_ollama_settings_are_read_from_the_environment() -> None:
    settings = ollama_settings_from_env(
        {"OLLAMA_HOST": "http://10.0.0.5:11434", "OLLAMA_MODEL": "llama3.1:8b", "OLLAMA_TIMEOUT": "45"}
    )
    assert (settings.host, settings.model, settings.timeout) == ("http://10.0.0.5:11434", "llama3.1:8b", 45.0)


def test_a_timeout_that_is_not_a_number_is_rejected_by_name() -> None:
    with pytest.raises(ValueError, match="OLLAMA_TIMEOUT"):
        ollama_settings_from_env({"OLLAMA_TIMEOUT": "soon"})


def test_the_default_provider_is_ollama_and_creating_it_does_not_connect() -> None:
    llm = llm_from_env({})
    assert isinstance(llm, OllamaLLM)
    assert llm.name == "ollama:qwen2.5:7b-instruct"


def test_the_fake_provider_is_the_scripted_model() -> None:
    assert isinstance(llm_from_env({"LLM_PROVIDER": "fake"}), ScriptedLLM)


def test_an_unknown_provider_is_rejected_with_the_valid_names() -> None:
    with pytest.raises(ValueError) as exc:
        llm_from_env({"LLM_PROVIDER": "gpt-cloud"})
    message = str(exc.value)
    assert "gpt-cloud" in message and all(name in message for name in PROVIDERS)
