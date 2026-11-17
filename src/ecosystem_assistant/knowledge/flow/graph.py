"""The informational flow as a LangGraph graph (design.md D-3, D-9).

langgraph 1.2 API, confirmed with a throwaway probe (task 1.2):
- ``StateGraph(State)`` over a ``TypedDict``; a field annotated ``Annotated[list[str], operator.add]``
  is appended to by every node that returns it (that is how the trace grows).
- ``add_node(name, fn)``; ``add_edge(START, "a")``; ``add_edge("a", "b")``; ``add_edge("b", END)``.
- ``add_conditional_edges("node", router_fn, {"label": "next_node", ...})`` where the router returns a label.
- ``graph.compile().invoke(initial_state)`` returns the final state as a dict.
  ``START`` and ``END`` come from ``langgraph.graph``.
"""
from __future__ import annotations

import operator
import os
from pathlib import Path
from typing import Annotated

# LangGraph pulls in LangSmith, a tracing service. Nothing may leave the machine, so it is forced off
# before LangGraph is imported (the documentation says so too).
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from langgraph.graph import END, START, StateGraph  # noqa: E402

from ecosystem_assistant.knowledge.flow.answer import Answer, PassageInfo, TraceStep, passage_info  # noqa: E402
from ecosystem_assistant.knowledge.flow.nodes import FlowNodes, FlowState  # noqa: E402
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph  # noqa: E402
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex  # noqa: E402
from ecosystem_assistant.llm.port import LLM  # noqa: E402

# Minimum score for a passage to count as evidence. Scores are not comparable across embedders, so each one
# has its own default. Calibrated on measured data (see tests/flow/test_calibration.py for the numbers):
#   hashing      relevant 0.13-0.54, off-topic 0.06-0.30  -> 0.15 (keeps 21 of 22 relevant, rejects 7 of 8 off-topic)
#   minilm-l6-v2 relevant 0.34-0.72, off-topic 0.09-0.18  -> 0.30 (keeps 22 of 22 relevant, rejects 8 of 8 off-topic)
# Questions about the domain whose answer is absent score as high as relevant ones; no threshold separates them.
DEFAULT_MIN_SCORES: dict[str, float] = {"hashing": 0.15, "minilm-l6-v2": 0.30}
BLANK_QUESTION_MESSAGE = "Please ask a question."


def default_min_score(embedder_name: str) -> float:
    if embedder_name not in DEFAULT_MIN_SCORES:
        raise ValueError(
            f"No calibrated minimum score for embedder {embedder_name!r}. Pass min_score explicitly, or calibrate "
            f"one (known embedders: {', '.join(sorted(DEFAULT_MIN_SCORES))})."
        )
    return DEFAULT_MIN_SCORES[embedder_name]


class _State(FlowState):
    trace: Annotated[list[TraceStep], operator.add]  # type: ignore[misc]


class InformationalFlow:
    """Answers any informational question through one pipeline: plan, graph, documents, answer, check."""

    def __init__(self, graph: KnowledgeGraph, index: RetrievalIndex, llm: LLM,
                 min_score: float | None = None, k: int = 5, data_root: Path | None = None) -> None:
        self.graph, self.index, self.llm = graph, index, llm
        self.data_root = Path(data_root) if data_root is not None else None
        self.min_score = default_min_score(index.embedder.name) if min_score is None else min_score
        self._compiled = self._build(FlowNodes(graph, index, llm, self.min_score, k))

    @staticmethod
    def _build(nodes: FlowNodes):
        builder = StateGraph(_State)
        builder.add_node("plan", nodes.plan)
        builder.add_node("graph_queries", nodes.graph_queries)
        builder.add_node("document_search", nodes.document_search)
        builder.add_node("answer", nodes.answer)
        builder.add_node("check", nodes.check)
        builder.add_node("insufficient", nodes.insufficient)
        builder.add_edge(START, "plan")
        builder.add_edge("plan", "graph_queries")
        builder.add_edge("graph_queries", "document_search")
        builder.add_conditional_edges("document_search", nodes.route,
                                      {"answer": "answer", "insufficient": "insufficient"})
        builder.add_edge("answer", "check")
        builder.add_edge("check", END)
        builder.add_edge("insufficient", END)
        return builder.compile()

    def ask(self, question: str) -> Answer:
        """Answer ``question``. An unreachable model raises ``LLMUnavailableError``; nothing replaces it silently."""
        question = (question or "").strip()
        if not question:
            return Answer("", BLANK_QUESTION_MESSAGE, "insufficient_evidence", False, [], [], self.llm.name)
        final = self._compiled.invoke({"question": question, "trace": []})
        result = final["result"]
        return Answer(
            question=question, text=result["text"], status=result["status"], grounded=result["grounded"],
            citations=list(result["citations"]), trace=list(final["trace"]), llm=self.llm.name,
            passages=self._passages(final),
        )

    def _passages(self, final: dict) -> list[PassageInfo]:
        """The retrieved passages; with a data root each is checked against its file for exactness."""
        search = final.get("search")
        found: list[PassageInfo] = []
        for passage in (search.passages if search is not None else []):
            file_text = None
            if self.data_root is not None:
                try:
                    file_text = (self.data_root / passage.path).read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    file_text = None
            found.append(passage_info(passage, file_text))
        return found
