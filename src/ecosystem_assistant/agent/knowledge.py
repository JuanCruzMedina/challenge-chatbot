"""The agent's one knowledge tool: the informational flow, refreshed before every question (design.md D-4, D-6)."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from langchain_core.tools import StructuredTool

from ecosystem_assistant.knowledge.flow.answer import Answer
from ecosystem_assistant.knowledge.flow.graph import InformationalFlow
from ecosystem_assistant.knowledge.graph.build import build_graph
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from ecosystem_assistant.llm.port import LLM

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_ROOT = REPO_ROOT / "var" / "workspace"
TOOL_NAME = "query_knowledge"

TOOL_DESCRIPTION = (
    "Answer a question about the company's documentation and architecture: services, APIs, events, owners and "
    "leads, applications and clients, features, product vision, runbooks and how things relate to each other. "
    "Use it for ANY question about facts or documentation. It only reads: it never changes anything. "
    "Its result has the answer (with [K1] / [D1] citations), a status, whether it is grounded, the sources "
    "of every citation, and the passages of documents it found (path, section, text and, for a service document, its "
    "service and doc_path, which is the path the write tools take). Pass the answer on to the "
    "person as it is, keep its citations and name its sources; do not add facts that are not in it. When you must "
    "change an existing document, quote the text to replace from a passage marked exact (not truncated)."
)

TOOL_SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string", "description": "The question, in the person's own words."}},
    "required": ["question"],
    "additionalProperties": False,
}


class KnowledgeService:
    """Answers questions from a data root, refreshing the graph and the index first so nothing is stale."""

    def __init__(self, data_root: Path, index: RetrievalIndex, llm: LLM,
                 min_score: float | None = None, k: int = 5) -> None:
        self.data_root = Path(data_root)
        self.index, self.llm, self.min_score, self.k = index, llm, min_score, k

    @classmethod
    def from_env(cls, llm: LLM | None = None) -> "KnowledgeService":
        """The real thing: the data root of ``AGENT_DATA_ROOT`` (default ``var/workspace``), the project's index."""
        from ecosystem_assistant.llm.settings import llm_from_env

        root = Path(os.environ.get("AGENT_DATA_ROOT") or DEFAULT_DATA_ROOT)
        if not (root / "company.yaml").is_file():
            raise FileNotFoundError(
                f"There is no ecosystem data in {root}. Create the workspace with: "
                f"uv run python scripts/seed_workspace.py"
            )
        return cls(root, RetrievalIndex(), llm or llm_from_env())

    def ask(self, question: str) -> Answer:
        """Rebuild the graph, synchronize the index (only changed files are embedded), then run the flow."""
        graph = build_graph(self.data_root)
        self.index.sync(self.data_root, graph)
        return InformationalFlow(graph, self.index, self.llm, min_score=self.min_score, k=self.k,
                                 data_root=self.data_root).ask(question)


def render(answer: Answer) -> str:
    """What the model is given: the answer, how far to trust it and where each citation comes from."""
    return json.dumps(
        {
            "answer": answer.text,
            "status": answer.status,
            "grounded": answer.grounded,
            "sources": [{"id": c.id, "kind": c.kind, "label": c.label, "sources": c.sources}
                        for c in answer.citations],
            "passages": [p.to_dict() for p in answer.passages],
        },
        ensure_ascii=False,
    )


def make_knowledge_tool(service: KnowledgeService) -> StructuredTool:
    async def query_knowledge(question: str) -> str:
        # The flow is synchronous and slow (model calls); keep the event loop free while it runs.
        return render(await asyncio.to_thread(service.ask, question))

    return StructuredTool(name=TOOL_NAME, description=TOOL_DESCRIPTION, args_schema=TOOL_SCHEMA,
                          coroutine=query_knowledge)
