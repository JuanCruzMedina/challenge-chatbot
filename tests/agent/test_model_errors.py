"""Spec: a model that cannot be reached, or that cannot call tools, is reported clearly and never replaced."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import ollama
import pytest
from langchain_ollama import ChatOllama

from ecosystem_assistant.agent.agent import Agent
from ecosystem_assistant.agent.knowledge import KnowledgeService
from ecosystem_assistant.agent.settings import AgentModelError, chat_model_from_env
from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from ecosystem_assistant.llm.port import LLMUnavailableError
from ecosystem_assistant.llm.scripted import ScriptedLLM
from tests.agent.conftest import run
from tests.agent.fake_chat import ScriptedChat, ai_text, ai_tool


def one_turn(chat: Any, workspace_dir: Path, audit_file: Path, tmp_path: Path, knowledge_llm: ScriptedLLM | None = None):
    service = KnowledgeService(workspace_dir, RetrievalIndex(tmp_path / "index", HashingEmbedder()),
                               knowledge_llm or ScriptedLLM(), min_score=0.0)

    async def scenario():
        async with Agent.open(chat=chat, workspace=workspace_dir, audit_file=audit_file, knowledge=service) as agent:
            return await agent.chat("anything")

    return run(scenario())


def test_an_unreachable_model_server_says_how_to_start_it(workspace_dir, audit_file, tmp_path) -> None:
    chat = ScriptedChat(script=[httpx.ConnectError("All connection attempts failed")])

    with pytest.raises(AgentModelError) as exc:
        one_turn(chat, workspace_dir, audit_file, tmp_path)

    message = str(exc.value)
    assert "ollama serve" in message and "http://localhost:11434" in message and "qwen2.5:7b-instruct" in message


def test_a_model_without_tool_support_names_the_model(workspace_dir, audit_file, tmp_path) -> None:
    error = ollama.ResponseError("registry.ollama.ai/library/tiny:1b does not support tools", 400)

    with pytest.raises(AgentModelError) as exc:
        one_turn(ScriptedChat(script=[error]), workspace_dir, audit_file, tmp_path)

    message = str(exc.value)
    assert "qwen2.5:7b-instruct" in message and "tool" in message.lower() and "OLLAMA_MODEL" in message


def test_a_model_that_is_not_pulled_says_which_one_to_pull(workspace_dir, audit_file, tmp_path) -> None:
    error = ollama.ResponseError("model 'qwen2.5:7b-instruct' not found", 404)
    with pytest.raises(AgentModelError, match="ollama pull qwen2.5:7b-instruct"):
        one_turn(ScriptedChat(script=[error]), workspace_dir, audit_file, tmp_path)


def test_an_error_that_is_not_about_the_model_server_is_not_disguised(workspace_dir, audit_file, tmp_path) -> None:
    with pytest.raises(ZeroDivisionError):
        one_turn(ScriptedChat(script=[ZeroDivisionError("a real bug")]), workspace_dir, audit_file, tmp_path)


def test_no_other_model_is_tried_and_no_tool_runs_when_the_model_is_down(workspace_dir, audit_file, tmp_path) -> None:
    chat = ScriptedChat(script=[httpx.ConnectError("down"), ai_text("this second answer must never be used")])
    with pytest.raises(AgentModelError):
        one_turn(chat, workspace_dir, audit_file, tmp_path)
    assert len(chat.seen) == 1 and not audit_file.exists()


def test_the_flows_unreachable_model_surfaces_as_the_same_clear_error(workspace_dir, audit_file, tmp_path) -> None:
    chat = ScriptedChat(script=[ai_tool("query_knowledge", {"question": "Who owns tracking?"}), ai_text("never")])
    flow_llm = ScriptedLLM([LLMUnavailableError("Cannot reach Ollama at http://x. Start it with `ollama serve`.")])

    with pytest.raises(LLMUnavailableError, match="ollama serve"):
        one_turn(chat, workspace_dir, audit_file, tmp_path, flow_llm)


# --- settings -----------------------------------------------------------------------------------------

def test_the_chat_model_comes_from_the_same_settings_as_the_flow() -> None:
    chat = chat_model_from_env({})
    assert isinstance(chat, ChatOllama)
    assert (chat.model, chat.base_url, chat.temperature) == ("qwen2.5:7b-instruct", "http://localhost:11434", 0)

    other = chat_model_from_env({"OLLAMA_MODEL": "llama3.1:8b", "OLLAMA_HOST": "http://10.0.0.5:11434",
                                 "OLLAMA_TIMEOUT": "30"})
    assert (other.model, other.base_url) == ("llama3.1:8b", "http://10.0.0.5:11434")
    assert other.client_kwargs.get("timeout") == 30.0
