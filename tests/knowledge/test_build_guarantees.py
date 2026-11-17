"""Spec: provenance on everything, deterministic builds, and dangling references fail loudly."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ecosystem_assistant.knowledge.graph.build import GraphBuildError, build_graph
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph
from tests.data.fixture import edit
from tests.data.helpers import SAMPLE, load_validator


def test_every_entity_and_relation_records_existing_source_files(sample_graph: KnowledgeGraph) -> None:
    exported = sample_graph.export()
    assert exported["nodes"] and exported["edges"]
    for item in exported["nodes"] + exported["edges"]:
        assert item["sources"], item
        for source in item["sources"]:
            assert not Path(source).is_absolute()
            assert (SAMPLE / source).is_file(), f"{source} listed as a source of {item.get('id') or item}"


def test_specific_sources(sample_graph: KnowledgeGraph) -> None:
    nodes = {n["id"]: n for n in sample_graph.nodes()}
    assert nodes["service:orders-service"]["sources"] == ["repos/orders-service/service.yaml"]
    assert nodes["feature:LOG-FEAT-101"]["sources"] == ["clients/demo-logistics/product/features.yaml"]
    assert nodes["client:demo-grocery"]["sources"] == ["company.yaml"]
    consumes = [e for e in sample_graph.edges("CONSUMES")
                if e["source"] == "service:orders-service" and e["target"] == "api:payments-api"]
    assert consumes[0]["sources"] == ["repos/orders-service/service.yaml"]


def test_building_twice_gives_the_same_graph(tmp_path: Path) -> None:
    copy = tmp_path / "copy"
    shutil.copytree(SAMPLE, copy)
    first, second = build_graph(SAMPLE).export(), build_graph(SAMPLE).export()
    assert first == second
    assert build_graph(copy).export() == first


@pytest.mark.parametrize(
    ("change", "needle"),
    [
        (lambda m: m.update(consumes_apis=["ghost-api"]), "ghost-api"),
        (lambda m: m.update(features=["GHOST-FEAT"]), "GHOST-FEAT"),
        (lambda m: m.update(application="ghost-app"), "ghost-app"),
        (lambda m: m.update(docs=["README.md", "docs/missing.md"]), "docs/missing.md"),
    ],
)
def test_a_dangling_reference_fails_the_build_naming_file_and_item(
    fx_root: Path, change, needle: str
) -> None:
    edit(fx_root / "repos" / "svc-a2" / "service.yaml", change)
    with pytest.raises(GraphBuildError) as exc:
        build_graph(fx_root)
    assert "repos/svc-a2/service.yaml" in str(exc.value)
    assert needle in str(exc.value)


def test_the_validator_and_the_builder_accept_the_same_data(fx_root: Path) -> None:
    validator = load_validator()
    for root in (SAMPLE, fx_root):
        assert validator.validate(root).errors == []
        assert build_graph(root).nodes()
