"""Spec: the knowledge tool reflects the current documents, never modifies the data, and leaves no trace in actions."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

from ecosystem_assistant.agent.knowledge import KnowledgeService, make_knowledge_tool
from ecosystem_assistant.agent.mcp_tools import McpToolbox
from ecosystem_assistant.knowledge.flow.catalog import PLAN_SCHEMA
from ecosystem_assistant.knowledge.retrieval.embedders import HashingEmbedder
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from ecosystem_assistant.llm.port import LLMUnavailableError
from ecosystem_assistant.llm.scripted import Call, ScriptedLLM
from tests.agent.conftest import run
from tests.data.fixture import edit

PLAN_NOTHING = {"graph_queries": []}
PLAN_OWNER = {"graph_queries": [{"method": "service_owner", "arguments": {"service": "tracking-service"}}]}


def oracle(plan: dict[str, Any] = PLAN_NOTHING):
    """Plans as told and answers by citing every piece of evidence it was given."""
    def respond(call: Call) -> Any:
        if call.schema == PLAN_SCHEMA:
            return plan
        cited = list(dict.fromkeys(re.findall(r"\[((?:K|D)\d+)\]", call.user.split("EVIDENCE", 1)[1])))
        return {"answer": "from the evidence " + " ".join(f"[{c}]" for c in cited), "citations": cited}
    return respond


def service_for(workspace_dir: Path, tmp_path: Path, plan: dict[str, Any] = PLAN_NOTHING) -> tuple[KnowledgeService, ScriptedLLM]:
    llm = ScriptedLLM(responder=oracle(plan))
    index = RetrievalIndex(tmp_path / "index", HashingEmbedder())
    return KnowledgeService(workspace_dir, index, llm, min_score=0.0), llm


def digest(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_a_document_created_through_an_mcp_tool_is_found_by_the_next_question(
    workspace_dir: Path, audit_file: Path, tmp_path: Path
) -> None:
    service, _ = service_for(workspace_dir, tmp_path)
    content = "# Zebra crossing protocol\n\n## Steps\nalways wait for the zebra signal before crossing\n"

    async def scenario():
        async with McpToolbox.stdio(workspace=workspace_dir, audit_file=audit_file) as box:
            add = next(t for t in box.tools if t.name == "add_document")
            await add.ainvoke({"service": "notifications-service", "doc_path": "docs/zebra.md", "content": content})
    before = service.ask("What is the zebra crossing protocol?")
    run(scenario())
    after = service.ask("What is the zebra crossing protocol?")

    new_path = "repos/notifications-service/docs/zebra.md"
    assert new_path not in {s for c in before.citations for s in c.sources}
    assert new_path in {s for c in after.citations for s in c.sources}


def test_an_edited_document_answers_with_its_new_text(workspace_dir: Path, tmp_path: Path) -> None:
    service, llm = service_for(workspace_dir, tmp_path)
    service.ask("How many requests per minute does the tracking api allow?")
    path = workspace_dir / "repos" / "tracking-service" / "docs" / "api.md"
    path.write_text(path.read_text(encoding="utf-8").replace("300 requests", "777 requests"), encoding="utf-8")

    service.ask("How many requests per minute does the tracking api allow?")

    last_answer_prompt = [c.user for c in llm.calls if c.kind == "json" and c.schema != PLAN_SCHEMA][-1]
    assert "777 requests" in last_answer_prompt and "300 requests" not in last_answer_prompt


def test_a_change_to_a_manifest_is_seen_by_the_graph_on_the_next_question(workspace_dir: Path, tmp_path: Path) -> None:
    service, llm = service_for(workspace_dir, tmp_path, PLAN_OWNER)
    service.ask("Who owns the tracking service?")
    edit(workspace_dir / "repos" / "tracking-service" / "service.yaml", lambda m: m.update(owner_team="radar-team"))

    service.ask("Who owns the tracking service?")

    last_answer_prompt = [c.user for c in llm.calls if c.kind == "json" and c.schema != PLAN_SCHEMA][-1]
    assert "radar-team" in last_answer_prompt


def test_asking_changes_nothing_in_the_data_and_leaves_the_actions_audit_empty(
    workspace_dir: Path, audit_file: Path, tmp_path: Path
) -> None:
    service, _ = service_for(workspace_dir, tmp_path, PLAN_OWNER)
    before = digest(workspace_dir)

    service.ask("Who owns the tracking service?")
    service.ask("What should I do when a vehicle disappears from the map?")

    assert digest(workspace_dir) == before
    assert not audit_file.exists()  # a knowledge question never reaches the actions server


def test_an_unreachable_model_is_not_swallowed(workspace_dir: Path, tmp_path: Path) -> None:
    llm = ScriptedLLM([LLMUnavailableError("Cannot reach Ollama at http://x. Start it with `ollama serve`.")])
    service = KnowledgeService(workspace_dir, RetrievalIndex(tmp_path / "index", HashingEmbedder()), llm, min_score=0.0)
    with pytest.raises(LLMUnavailableError, match="ollama serve"):
        service.ask("Who owns the tracking service?")


# --- the LangChain tool ------------------------------------------------------------------------------

def test_the_knowledge_tool_has_one_question_argument_and_a_useful_description(workspace_dir: Path, tmp_path: Path) -> None:
    service, _ = service_for(workspace_dir, tmp_path)
    tool = make_knowledge_tool(service)

    assert tool.name == "query_knowledge"
    assert tool.args_schema["required"] == ["question"] and set(tool.args_schema["properties"]) == {"question"}
    assert tool.args_schema["additionalProperties"] is False
    for word in ("documentation", "read", "never change"):
        assert word in tool.description.lower()


def test_the_tool_returns_the_answer_status_grounded_flag_and_sources_as_json(workspace_dir: Path, tmp_path: Path) -> None:
    service, _ = service_for(workspace_dir, tmp_path, PLAN_OWNER)
    tool = make_knowledge_tool(service)

    result = json.loads(run(tool.ainvoke({"question": "Who owns the tracking service?"})))

    assert set(result) == {"answer", "status", "grounded", "sources"}
    assert result["status"] == "answered" and result["grounded"] is True
    assert "[K1]" in result["answer"]
    k1 = next(s for s in result["sources"] if s["id"] == "K1")
    assert k1["kind"] == "graph" and k1["sources"] == ["repos/tracking-service/service.yaml"]


def test_the_tool_does_not_hide_an_unreachable_model(workspace_dir: Path, tmp_path: Path) -> None:
    llm = ScriptedLLM([LLMUnavailableError("Cannot reach Ollama. Start it with `ollama serve`.")])
    service = KnowledgeService(workspace_dir, RetrievalIndex(tmp_path / "index", HashingEmbedder()), llm, min_score=0.0)
    with pytest.raises(LLMUnavailableError):
        run(make_knowledge_tool(service).ainvoke({"question": "anything"}))
