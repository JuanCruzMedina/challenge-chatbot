"""The stages of the pipeline as functions over a shared state (design.md D-3).

Each node returns only the keys it changes; ``trace`` is appended to by every node.
"""
from __future__ import annotations

from typing import Any, TypedDict

from ecosystem_assistant.knowledge.flow.answer import (
    INSUFFICIENT_MESSAGE,
    Draft,
    TraceStep,
    finalize_answer,
    write_answer,
)
from ecosystem_assistant.knowledge.flow.evidence import (
    Evidence,
    Fact,
    SearchResult,
    build_evidence,
    has_evidence,
    run_graph_queries,
    search_documents,
)
from ecosystem_assistant.knowledge.flow.plan import PlanOutcome, make_plan
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from ecosystem_assistant.llm.port import LLM


class FlowState(TypedDict, total=False):
    question: str
    outcome: PlanOutcome
    facts: list[Fact]
    search: SearchResult
    evidence: Evidence
    draft: Draft
    result: dict[str, Any]
    trace: list[TraceStep]  # replaced by an appending reducer when the graph is built


class FlowNodes:
    def __init__(self, graph: KnowledgeGraph, index: RetrievalIndex, llm: LLM, min_score: float, k: int) -> None:
        self.graph, self.index, self.llm, self.min_score, self.k = graph, index, llm, min_score, k

    def plan(self, state: FlowState) -> dict[str, Any]:
        outcome = make_plan(self.llm, self.graph, state["question"])
        plan = outcome.plan
        label = "degraded" if outcome.degraded else ("retried" if outcome.attempts == 2 else "ok")
        details = {
            "attempts": outcome.attempts,
            "queries": [{"method": q.method, "arguments": q.arguments} for q in plan.graph_queries],
            "filters": dict(plan.filters),
            "include_obsolete": plan.include_obsolete,
            "dropped": [{"item": d.item, "reason": d.reason} for d in plan.dropped],
            "cut": plan.cut,
            "error": outcome.error,
        }
        return {"outcome": outcome, "trace": [TraceStep("plan", label, details)]}

    def graph_queries(self, state: FlowState) -> dict[str, Any]:
        facts = run_graph_queries(self.graph, state["outcome"].plan.graph_queries)
        executed = [{"id": f.id, "method": f.method, "found": f.found, "truncated": f.truncated} for f in facts]
        step = TraceStep("graph_queries", f"{len(facts)} queries", {"executed": executed})
        return {"facts": facts, "trace": [step]}

    def document_search(self, state: FlowState) -> dict[str, Any]:
        plan = state["outcome"].plan
        search = search_documents(self.index, state["question"], plan, self.min_score, self.k)
        details = {
            "searched": search.searched, "kept": len(search.passages), "below_threshold": search.below_threshold,
            "min_score": self.min_score, "filters": dict(plan.filters), "include_obsolete": plan.include_obsolete,
        }
        step = TraceStep("document_search", f"{len(search.passages)} passages", details)
        return {"search": search, "trace": [step]}

    def route(self, state: FlowState) -> str:
        """A sufficiency guard on the data (not a choice between informational and action routes)."""
        return "answer" if has_evidence(state["facts"], state["search"].passages) else "insufficient"

    def answer(self, state: FlowState) -> dict[str, Any]:
        evidence = build_evidence(state["facts"], state["search"].passages)
        draft = write_answer(self.llm, state["question"], evidence.text)
        details = {"attempts": draft.attempts, "evidence_chars": len(evidence.text),
                   "dropped_passages": evidence.dropped_passages, "error": draft.error}
        step = TraceStep("answer", "failed" if draft.failed else "ok", details)
        return {"evidence": evidence, "draft": draft, "trace": [step]}

    def check(self, state: FlowState) -> dict[str, Any]:
        stage = finalize_answer(state["draft"], state["evidence"])
        degraded = state["outcome"].degraded or stage.status == "degraded"
        status = "degraded" if degraded else "answered"
        details = {"removed": stage.removed, "grounded": stage.grounded,
                   "citations": [c.id for c in stage.citations], "status": status}
        result = {"text": stage.text, "status": status, "grounded": stage.grounded, "citations": stage.citations}
        return {"result": result, "trace": [TraceStep("check", status, details)]}

    def insufficient(self, state: FlowState) -> dict[str, Any]:
        result = {"text": INSUFFICIENT_MESSAGE, "status": "insufficient_evidence", "grounded": False,
                  "citations": []}
        steps = [TraceStep("answer", "skipped", {"reason": "no graph fact and no passage reached the minimum score"}),
                 TraceStep("check", "skipped", {})]
        return {"result": result, "trace": steps}
