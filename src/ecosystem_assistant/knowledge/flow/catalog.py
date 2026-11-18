"""The fixed catalog of graph questions the model may plan, and the JSON schema of a plan (design.md D-4)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_QUERIES = 4


@dataclass(frozen=True)
class QuerySpec:
    method: str
    required: tuple[str, ...]
    description: str


CATALOG: dict[str, QuerySpec] = {
    spec.method: spec
    for spec in (
        QuerySpec("client_overview", ("client",), "applications and services of a client, and its product vision"),
        QuerySpec("application_services", ("application",), "services of an application and its client"),
        QuerySpec("service_owner", ("service",), "owning team and tech lead of a service"),
        QuerySpec("api_consumers", ("api",), "services that provide and consume an API, with deprecated versions"),
        QuerySpec("event_flow", ("event",), "services that publish and subscribe to an event"),
        QuerySpec("service_product_context", ("service",),
                  "application, client, features and product vision of a service"),
        QuerySpec("relation_path", ("start", "end"), "shortest chain of relations between two entities"),
        QuerySpec("describe", ("entity",), "every relation of one entity"),
        QuerySpec("obsolete_documents", (), "documents marked as obsolete"),
        QuerySpec("list_entities", ("type",),
                  "every entity of one type (team, person, service, client, application, api, event, feature)"),
        QuerySpec("team_overview", ("team",), "services a team owns and the person who leads each"),
        QuerySpec("documents_about", ("entity",),
                  "documents that say they are about a service, API or event, and the documents of a service"),
        QuerySpec("teams_overview", (), "every team with its services and the person who leads each (all teams at once)"),
    )
}

PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "graph_queries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": sorted(CATALOG)},
                    "arguments": {"type": "object", "additionalProperties": {"type": "string"}},
                },
                "required": ["method", "arguments"],
            },
        },
        "filters": {
            "type": "object",
            "properties": {
                "client": {"type": "string"},
                "application": {"type": "string"},
                "service": {"type": "string"},
            },
        },
        "include_obsolete": {"type": "boolean"},
    },
    "required": ["graph_queries"],
}


def describe_catalog() -> str:
    """The catalog as text for the planning prompt, one line per method."""
    lines = []
    for spec in CATALOG.values():
        arguments = ", ".join(spec.required) or "no arguments"
        lines.append(f"- {spec.method}({arguments}): {spec.description}")
    return "\n".join(lines)
