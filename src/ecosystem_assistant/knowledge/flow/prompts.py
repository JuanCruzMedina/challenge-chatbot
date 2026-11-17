"""Prompts of the informational flow, as versioned English constants (design.md D-7)."""
from __future__ import annotations

from typing import Any

from ecosystem_assistant.knowledge.flow.catalog import MAX_QUERIES, describe_catalog
from ecosystem_assistant.knowledge.graph import model as graph_model
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph

PROMPTS_VERSION = "1"

# --- planning ----------------------------------------------------------------------------------

PLAN_SYSTEM = """You plan how to answer a question about a software company's documentation and architecture.
Two sources exist: a knowledge graph of facts (ownership, dependencies, events, features) and the text of
the documents. The documents are always searched for you; you only choose graph questions.

Reply with one JSON object with these keys:
- "graph_queries": a list of at most {max_queries} items {{"method": ..., "arguments": {{...}}}}. Use only these methods,
  with exactly these argument names, each argument being a name taken from the question:
{catalog}
  Use an empty list when the graph cannot help.
- "filters": optional {{"client", "application", "service"}} to restrict the document search when the question is
  clearly about one of them.
- "include_obsolete": true only when the question asks about old, deprecated or replaced documents.

Known clients: {clients}
Known applications: {applications}
Known services: {services}
"""


def plan_system(graph: KnowledgeGraph) -> str:
    names = lambda kind: ", ".join(sorted(n["id"].split(":", 1)[1] for n in graph.nodes(kind)))  # noqa: E731
    return PLAN_SYSTEM.format(
        max_queries=MAX_QUERIES,
        catalog=describe_catalog(),
        clients=names(graph_model.CLIENT),
        applications=names(graph_model.APPLICATION),
        services=names(graph_model.SERVICE),
    )


def plan_user(question: str, previous_error: str | None = None) -> str:
    text = f"Question: {question}"
    if previous_error:
        text += (
            f"\n\nYour previous answer was not valid: {previous_error}\n"
            "Reply again with a valid JSON object only, following the format you were given."
        )
    return text


# --- answering ---------------------------------------------------------------------------------

ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "citations"],
}

ANSWER_SYSTEM = """You answer questions about a software company's documentation and architecture.
Use ONLY the evidence you are given: graph facts numbered K1, K2... and document passages numbered D1, D2...
Rules:
- Cite every statement with the id of the evidence that supports it, like [K1] or [D2]. Cite only ids that exist.
- If the evidence does not answer the question, or only partly, say exactly what is missing. Never guess and never
  add names, numbers or procedures that are not in the evidence.
- A fact that says "Not found" means the name was not recognized: say so and mention the close names it lists.
- Be concise: a few sentences, in the language of the question.

Reply with one JSON object: {"answer": "<text with inline [K1]/[D2] citations>", "citations": ["K1", "D2"]}
where "citations" lists every id you cited."""


def answer_user(question: str, evidence_text: str, previous_error: str | None = None) -> str:
    text = f"Question: {question}\n\nEVIDENCE\n{evidence_text}"
    if previous_error:
        text += (
            f"\n\nYour previous answer was not valid: {previous_error}\n"
            "Reply again with a valid JSON object only, following the format you were given."
        )
    return text
