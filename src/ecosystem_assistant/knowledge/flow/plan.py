"""Planning: ask the model for a plan, validate it before anything runs (design.md D-4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ecosystem_assistant.knowledge.flow import prompts
from ecosystem_assistant.knowledge.flow.catalog import CATALOG, MAX_QUERIES, PLAN_SCHEMA
from ecosystem_assistant.knowledge.graph import model as graph_model
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from ecosystem_assistant.llm.port import LLM, LLMOutputError

FILTER_KINDS = {"client": graph_model.CLIENT, "application": graph_model.APPLICATION, "service": graph_model.SERVICE}


@dataclass(frozen=True)
class PlannedQuery:
    method: str
    arguments: dict[str, str]


@dataclass(frozen=True)
class Dropped:
    item: str
    reason: str


@dataclass
class Plan:
    graph_queries: list[PlannedQuery] = field(default_factory=list)
    filters: dict[str, str] = field(default_factory=dict)
    include_obsolete: bool = False
    dropped: list[Dropped] = field(default_factory=list)
    cut: int = 0


@dataclass
class PlanOutcome:
    plan: Plan
    attempts: int
    degraded: bool = False
    error: str = ""


def validate_plan(raw: dict[str, Any], graph: KnowledgeGraph) -> Plan:
    """Keep what the catalog allows, drop the rest with a reason, cut to the limit, resolve the filters."""
    plan = Plan()

    queries = raw.get("graph_queries", [])
    if not isinstance(queries, list):
        plan.dropped.append(Dropped(repr(queries)[:60], "graph_queries is not a list"))
        queries = []
    valid: list[PlannedQuery] = []
    for entry in queries:
        label = repr(entry)[:80]
        if not isinstance(entry, dict):
            plan.dropped.append(Dropped(label, "the query is not an object"))
            continue
        method, arguments = entry.get("method"), entry.get("arguments", {})
        if method not in CATALOG:
            plan.dropped.append(Dropped(label, f"unknown method {method!r}"))
            continue
        if not isinstance(arguments, dict):
            plan.dropped.append(Dropped(label, "arguments is not an object"))
            continue
        spec = CATALOG[method]
        missing = [name for name in spec.required if name not in arguments]
        extra = [name for name in arguments if name not in spec.required]
        bad = [name for name, value in arguments.items()
               if name in spec.required and (not isinstance(value, str) or not value.strip())]
        if missing:
            plan.dropped.append(Dropped(label, f"missing argument(s) {', '.join(missing)} for {method}"))
        elif extra:
            plan.dropped.append(Dropped(label, f"unexpected argument(s) {', '.join(extra)} for {method}"))
        elif bad:
            plan.dropped.append(Dropped(label, f"argument(s) {', '.join(bad)} must be non-empty text"))
        else:
            valid.append(PlannedQuery(method, {k: v.strip() for k, v in arguments.items()}))
    plan.graph_queries = valid[:MAX_QUERIES]
    for extra_query in valid[MAX_QUERIES:]:
        plan.cut += 1
        plan.dropped.append(Dropped(f"{extra_query.method}({extra_query.arguments})",
                                    f"cut: a plan runs at most {MAX_QUERIES} graph queries"))

    filters = raw.get("filters", {})
    if isinstance(filters, dict):
        for kind, value in filters.items():
            if kind not in FILTER_KINDS:
                plan.dropped.append(Dropped(f"filter {kind}={value!r}", f"unknown filter kind {kind!r}"))
                continue
            candidates = graph.find_entities(value, type=FILTER_KINDS[kind], limit=1) if isinstance(value, str) else []
            if not candidates:
                plan.dropped.append(Dropped(f"filter {kind}={value!r}", f"unknown {kind} {value!r}"))
                continue
            plan.filters[kind] = graph_model.split_key(candidates[0].id)[1]
    elif filters:
        plan.dropped.append(Dropped(repr(filters)[:60], "filters is not an object"))

    plan.include_obsolete = raw.get("include_obsolete") is True
    return plan


def make_plan(llm: LLM, graph: KnowledgeGraph, question: str) -> PlanOutcome:
    """Ask for a plan; retry once when the answer is not valid JSON; then fall back to a document search alone.

    An unreachable model (``LLMUnavailableError``) is not caught: nothing replaces a broken setup silently.
    """
    system = prompts.plan_system(graph)
    error = ""
    for attempt in (1, 2):
        try:
            raw = llm.complete_json(system, prompts.plan_user(question, error or None), PLAN_SCHEMA)
        except LLMOutputError as exc:
            error = str(exc)
            continue
        return PlanOutcome(validate_plan(raw, graph), attempts=attempt)
    return PlanOutcome(Plan(), attempts=2, degraded=True, error=error)
