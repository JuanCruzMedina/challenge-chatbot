"""Spec: LLM_PROVIDER chooses the model of the flow and of the agent; the default stays local."""
from __future__ import annotations

from pathlib import Path

import pytest
from langchain_ollama import ChatOllama

from ecosystem_assistant.agent.settings import chat_model_from_env
from ecosystem_assistant.llm.anthropic_chat import SessionChatAnthropic
from ecosystem_assistant.llm.anthropic_llm import AnthropicLLM
from ecosystem_assistant.llm.ollama_llm import OllamaLLM
from ecosystem_assistant.llm.pricing import UnknownModelError
from ecosystem_assistant.llm.settings import PROVIDERS, llm_from_env


def test_anthropic_is_a_listed_provider() -> None:
    assert "anthropic" in PROVIDERS and PROVIDERS[0] == "ollama"


def test_anthropic_selects_the_adapter_for_the_flow_and_the_chat_model_for_the_agent(tmp_path: Path) -> None:
    env = {"LLM_PROVIDER": "anthropic", "ANTHROPIC_LEDGER": str(tmp_path / "l.json")}

    flow, agent = llm_from_env(env), chat_model_from_env(env)

    assert isinstance(flow, AnthropicLLM) and flow.name == "anthropic:claude-haiku-5-5"
    assert isinstance(agent, SessionChatAnthropic) and agent.model == "claude-haiku-5-5"
    assert not (tmp_path / "l.json").exists()  # creating them touches nothing


def test_both_paths_share_the_ledger_file_and_the_cap_of_the_environment(tmp_path: Path) -> None:
    env = {"LLM_PROVIDER": "anthropic", "ANTHROPIC_LEDGER": str(tmp_path / "shared.json"), "ANTHROPIC_MAX_USD": "2"}

    flow = llm_from_env(env)

    assert flow.ledger.path == tmp_path / "shared.json" and flow.ledger.cap_usd == 2.0
    assert chat_model_from_env(env).callbacks[0].ledger.path == tmp_path / "shared.json"


def test_without_the_variable_both_stay_local() -> None:
    assert isinstance(llm_from_env({}), OllamaLLM)
    assert isinstance(chat_model_from_env({}), ChatOllama)


def test_an_unknown_provider_lists_the_valid_ones_for_the_flow_and_for_the_agent() -> None:
    with pytest.raises(ValueError, match="gpt-cloud.*ollama"):
        llm_from_env({"LLM_PROVIDER": "gpt-cloud"})
    with pytest.raises(ValueError, match="gpt-cloud.*ollama.*anthropic"):
        chat_model_from_env({"LLM_PROVIDER": "gpt-cloud"})


def test_the_fake_provider_has_no_chat_model_for_the_agent() -> None:
    with pytest.raises(ValueError, match="fake"):
        chat_model_from_env({"LLM_PROVIDER": "fake"})


def test_the_model_can_be_chosen_only_among_priced_models(tmp_path: Path) -> None:
    env = {"LLM_PROVIDER": "anthropic", "ANTHROPIC_MODEL": "claude-opus-5-5", "ANTHROPIC_LEDGER": str(tmp_path / "l")}
    with pytest.raises(UnknownModelError):
        llm_from_env(env)
    with pytest.raises(UnknownModelError):
        chat_model_from_env(env)
