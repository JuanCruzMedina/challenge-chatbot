"""The answer stage: ask the model, check the citations, fall back to the evidence (design.md D-7, D-8)."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from ecosystem_assistant.knowledge.flow import prompts
from ecosystem_assistant.knowledge.flow.evidence import Evidence, Fact, Passage
from ecosystem_assistant.llm.port import LLM, LLMError, LLMOutputError, LLMUnavailableError

INSUFFICIENT_MESSAGE = "I could not find information about that in the documentation or the knowledge graph."
EVIDENCE_ONLY_PASSAGES = 3
EVIDENCE_ONLY_CHARS = 300

_ID = re.compile(r"([KkDd])\s*(\d+)")
_INLINE = re.compile(r"\[\s*([KkDd]\s*\d+)\s*\]")


@dataclass(frozen=True)
class Citation:
    id: str
    kind: str              # "graph" or "document"
    label: str
    sources: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Draft:
    text: str = ""
    citation_ids: list[str] = field(default_factory=list)
    attempts: int = 1
    failed: bool = False
    error: str = ""


@dataclass
class CheckResult:
    citations: list[Citation]
    removed: list[str]
    grounded: bool


@dataclass
class StageResult:
    text: str
    status: str            # "answered" or "degraded"
    grounded: bool
    citations: list[Citation]
    removed: list[str]
    attempts: int
    error: str = ""


# --- asking the model ------------------------------------------------------------------------------

def _read_draft(raw: dict[str, Any]) -> tuple[str, list[str]]:
    answer, citations = raw.get("answer"), raw.get("citations", [])
    if not isinstance(answer, str) or not answer.strip():
        raise LLMOutputError("the 'answer' field must be non-empty text")
    if not isinstance(citations, list) or not all(isinstance(c, str) for c in citations):
        raise LLMOutputError("the 'citations' field must be a list of ids such as K1 or D2")
    return answer.strip(), citations


def write_answer(llm: LLM, question: str, evidence_text: str) -> Draft:
    """Ask for ``{answer, citations}``; retry once when the output is invalid or the call fails.

    An unreachable model is not retried and not hidden: ``LLMUnavailableError`` propagates.
    """
    error = ""
    for attempt in (1, 2):
        try:
            raw = llm.complete_json(prompts.ANSWER_SYSTEM,
                                    prompts.answer_user(question, evidence_text, error or None),
                                    prompts.ANSWER_SCHEMA)
            text, ids = _read_draft(raw)
        except LLMUnavailableError:
            raise
        except LLMError as exc:
            error = str(exc)
            continue
        return Draft(text, ids, attempt)
    return Draft(attempts=2, failed=True, error=error)


# --- checking citations -----------------------------------------------------------------------------

def _normalize(raw: str) -> str:
    match = _ID.search(raw)
    return f"{match.group(1).upper()}{match.group(2)}" if match else raw.strip()


def check_citations(text: str, citation_ids: list[str], facts: list[Fact], passages: list[Passage]) -> CheckResult:
    """Keep the citations that exist, resolve them to their sources, and record the ones that do not exist."""
    by_fact = {f.id: f for f in facts}
    by_passage = {p.id: p for p in passages}
    candidates: list[str] = []
    for raw in [*citation_ids, *_INLINE.findall(text)]:
        candidate = _normalize(raw)
        if candidate not in candidates:
            candidates.append(candidate)

    citations: list[Citation] = []
    removed: list[str] = []
    for candidate in candidates:
        if candidate in by_fact:
            fact = by_fact[candidate]
            arguments = ", ".join(f"{k}={v}" for k, v in fact.arguments.items())
            citations.append(Citation(candidate, "graph", f"{fact.method}({arguments})", list(fact.sources)))
        elif candidate in by_passage:
            passage = by_passage[candidate]
            citations.append(Citation(candidate, "document", f"{passage.path} | {passage.heading_path}", [passage.path]))
        else:
            removed.append(candidate)
    return CheckResult(citations, removed, grounded=bool(citations))


# --- falling back to the evidence ------------------------------------------------------------------

def evidence_only_text(facts: list[Fact], passages: list[Passage]) -> str:
    """An answer built from the evidence itself, for when the model cannot write one. Deterministic."""
    lines = ["I could not write a summary, so here is the evidence I found."]
    found = [f for f in facts if f.found]
    if found:
        lines.append("Graph facts:")
        for fact in found:
            arguments = ", ".join(f"{k}={v}" for k, v in fact.arguments.items())
            lines.append(f"- {fact.method}({arguments}): {fact.text} [sources: {', '.join(fact.sources)}]")
    if passages:
        lines.append("Documents:")
        for passage in passages[:EVIDENCE_ONLY_PASSAGES]:
            body = passage.text.split("\n\n", 1)[-1].strip().replace("\n", " ")
            lines.append(f"- {passage.path} | {passage.heading_path}: {body[:EVIDENCE_ONLY_CHARS]}")
    return "\n".join(lines)


def run_answer_stage(llm: LLM, question: str, evidence: Evidence) -> StageResult:
    """Write the answer with the model and check it; when the model fails twice, answer from the evidence."""
    return finalize_answer(write_answer(llm, question, evidence.text), evidence)


def finalize_answer(draft: Draft, evidence: Evidence) -> StageResult:
    """The check stage: validate the draft's citations, or build the evidence-only answer for a failed draft."""
    if draft.failed:
        shown_facts = [f for f in evidence.facts if f.found]
        shown_passages = evidence.passages[:EVIDENCE_ONLY_PASSAGES]
        ids = [f.id for f in shown_facts] + [p.id for p in shown_passages]
        check = check_citations("", ids, shown_facts, shown_passages)
        return StageResult(evidence_only_text(evidence.facts, evidence.passages), "degraded", False,
                           check.citations, [], draft.attempts, draft.error)
    check = check_citations(draft.text, draft.citation_ids, evidence.facts, evidence.passages)
    return StageResult(draft.text, "answered", check.grounded, check.citations, check.removed, draft.attempts)


# --- the result of the whole flow ---------------------------------------------------------------------

@dataclass
class TraceStep:
    stage: str                      # plan, graph_queries, document_search, answer or check
    outcome: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Answer:
    question: str
    text: str
    status: str                     # "answered", "insufficient_evidence" or "degraded"
    grounded: bool
    citations: list[Citation]
    trace: list[TraceStep]
    llm: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
