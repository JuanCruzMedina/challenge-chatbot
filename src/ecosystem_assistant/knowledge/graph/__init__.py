"""In-memory knowledge graph of the ecosystem, built from the sample data (read-only).

    from ecosystem_assistant.knowledge.graph import build_graph
    graph = build_graph(data_root)
    graph.api_consumers("payments api").to_dict()
"""
from ecosystem_assistant.knowledge.graph.build import GraphBuildError, build_graph
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph, NotFound

__all__ = ["GraphBuildError", "KnowledgeGraph", "NotFound", "build_graph"]
