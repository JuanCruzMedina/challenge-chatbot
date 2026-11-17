"""Spec: only the intended files are indexed, and every chunk carries its scope and graph metadata."""
from __future__ import annotations

from pathlib import Path

import pytest

from ecosystem_assistant.knowledge.graph.build import build_graph
from ecosystem_assistant.knowledge.retrieval.documents import ServiceContext, discover_documents, load_chunks
from tests.data.fixture import edit, write_text
from tests.data.helpers import SAMPLE


@pytest.fixture
def root(fx_root: Path) -> Path:
    """The synthetic dataset plus files that must NOT or need not be indexed."""
    # The shared synthetic documents hold only a title; give two of them a body, which is what gets chunked.
    write_text(fx_root / "repos" / "svc-a1" / "docs" / "api.md", "# a1-api\n\n## Endpoints\nlists the widgets\n")
    write_text(fx_root / "repos" / "svc-a2" / "README.md", "# svc-a2\n\nConsumes the a1 api.\n")
    write_text(fx_root / "repos" / "svc-a1" / "docs" / ".hidden.md", "# hidden\n\nnope\n")
    write_text(fx_root / "repos" / "svc-a1" / "docs" / ".tmp-abc.part", "partial write\n")
    write_text(fx_root / "repos" / "svc-a1" / "docs" / "notes.txt", "not markdown\n")
    write_text(fx_root / "prs" / "pr-1" / "files" / "docs" / "new.md", "# new in a PR\n\ntext\n")
    write_text(fx_root / "repos" / "svc-ghost" / "README.md", "# svc-ghost\n\nA folder the graph does not know.\n")
    return fx_root


def context_of(root: Path) -> ServiceContext:
    return ServiceContext.from_graph(build_graph(root))


def test_only_the_intended_files_are_indexed(root: Path) -> None:
    found = discover_documents(root)

    assert found == sorted(found)
    assert "repos/svc-a1/README.md" in found and "repos/svc-a1/docs/api.md" in found
    assert "clients/client-a/product/vision.md" in found and "clients/client-b/product/vision.md" in found
    assert "company/overview.md" in found
    assert "repos/svc-ghost/README.md" in found
    assert not any(p.startswith("prs/") for p in found)
    assert not any("/." in p or p.startswith(".") for p in found)
    assert all(p.endswith(".md") for p in found)


def test_the_committed_data_has_22_indexed_documents_and_none_from_prs() -> None:
    found = discover_documents(SAMPLE)
    assert len(found) == 22
    assert {p.split("/")[0] for p in found} == {"repos", "clients", "company"}


def test_a_service_document_carries_service_application_and_client(root: Path) -> None:
    chunks = load_chunks(root, "repos/svc-a1/docs/api.md", context_of(root))

    assert chunks
    for c in chunks:
        assert (c.scope, c.service, c.application, c.client, c.chunk.status) == (
            "service", "svc-a1", "app-a1", "client-a", "current")


def test_a_client_document_has_a_client_and_no_service(root: Path) -> None:
    chunks = load_chunks(root, "clients/client-b/product/vision.md", context_of(root))
    assert {(c.scope, c.service, c.application, c.client) for c in chunks} == {("client", "", "", "client-b")}


def test_the_company_overview_has_neither(root: Path) -> None:
    chunks = load_chunks(root, "company/overview.md", context_of(root))
    assert {(c.scope, c.service, c.application, c.client) for c in chunks} == {("company", "", "", "")}


def test_a_folder_the_graph_does_not_know_is_still_indexed_with_empty_context(root: Path) -> None:
    chunks = load_chunks(root, "repos/svc-ghost/README.md", context_of(root))
    assert {(c.scope, c.service, c.application, c.client) for c in chunks} == {("service", "svc-ghost", "", "")}


def test_a_folder_named_like_part_of_a_known_service_is_not_confused_with_it(root: Path) -> None:
    write_text(root / "repos" / "svc" / "README.md", "# svc\n\nA folder whose name is only part of another.\n")
    chunks = load_chunks(root, "repos/svc/README.md", context_of(root))
    assert {(c.service, c.application, c.client) for c in chunks} == {("svc", "", "")}


def test_the_committed_orders_document_has_the_expected_metadata() -> None:
    context = ServiceContext.from_graph(build_graph(SAMPLE))
    chunks = load_chunks(SAMPLE, "repos/orders-service/docs/api.md", context)

    assert {(c.scope, c.service, c.application, c.client, c.chunk.status, c.chunk.title) for c in chunks} == {
        ("service", "orders-service", "storefront", "demo-grocery", "current", "orders-api v1")
    }
    assert {c.version for c in chunks} and all(len(c.version) == 64 for c in chunks)


def test_metadata_has_every_field_the_index_filters_and_cites_on(root: Path) -> None:
    chunk = load_chunks(root, "repos/svc-a1/docs/api.md", context_of(root))[0]
    assert set(chunk.metadata()) >= {
        "path", "title", "heading_path", "scope", "service", "application", "client", "status",
        "content_hash", "version", "chunk_index",
    }
    assert all(isinstance(v, (str, int)) for v in chunk.metadata().values())  # what the vector store accepts


def test_the_version_changes_when_the_context_changes_even_if_the_file_does_not(root: Path) -> None:
    before = load_chunks(root, "repos/svc-a2/README.md", context_of(root))[0]
    edit(root / "repos" / "svc-a2" / "service.yaml", lambda m: m.update(application="app-a1"))
    after = load_chunks(root, "repos/svc-a2/README.md", context_of(root))[0]

    assert before.chunk.content_hash == after.chunk.content_hash
    assert before.application == "app-a2" and after.application == "app-a1"
    assert before.version != after.version
