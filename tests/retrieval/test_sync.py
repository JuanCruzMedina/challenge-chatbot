"""Spec: the index follows the files incrementally (embedding only what changed)."""
from __future__ import annotations

from pathlib import Path

import pytest

from ecosystem_assistant.actions.tools.documents import set_obsolete
from ecosystem_assistant.actions.workspace import Workspace
from ecosystem_assistant.knowledge.graph.build import GraphBuildError
from ecosystem_assistant.knowledge.retrieval.documents import discover_documents
from ecosystem_assistant.knowledge.retrieval.index import RetrievalIndex
from tests.data.fixture import edit, write_text
from tests.data.helpers import SAMPLE
from tests.retrieval.helpers import CountingEmbedder, populate


@pytest.fixture
def root(fx_root: Path) -> Path:
    populate(fx_root)
    return fx_root


@pytest.fixture
def embedder() -> CountingEmbedder:
    return CountingEmbedder()


@pytest.fixture
def index(tmp_path: Path, embedder: CountingEmbedder) -> RetrievalIndex:
    return RetrievalIndex(tmp_path / "index", embedder)


def test_the_first_sync_indexes_every_document_of_the_committed_data(tmp_path: Path) -> None:
    embedder = CountingEmbedder()
    index = RetrievalIndex(tmp_path / "index", embedder)

    report = index.sync(SAMPLE)

    assert (report.added, report.updated, report.removed, report.unchanged) == (22, 0, 0, 0)
    assert report.chunks_embedded == len(embedder.seen) == index.chunk_count() > 22
    assert set(index.stored_versions()) == set(discover_documents(SAMPLE))


def test_a_second_sync_changes_nothing_and_embeds_nothing(
    index: RetrievalIndex, embedder: CountingEmbedder, root: Path
) -> None:
    first = index.sync(root)
    embedded_before = len(embedder.seen)

    second = index.sync(root)

    assert (second.added, second.updated, second.removed) == (0, 0, 0)
    assert second.unchanged == first.added
    assert second.chunks_embedded == 0 and len(embedder.seen) == embedded_before


def test_an_edited_file_is_re_embedded_alone(index: RetrievalIndex, embedder: CountingEmbedder, root: Path) -> None:
    index.sync(root)
    embedder.seen.clear()
    path = root / "repos" / "svc-a1" / "docs" / "api.md"
    path.write_text(path.read_text(encoding="utf-8").replace("widgets", "gadgets"), encoding="utf-8")

    report = index.sync(root)

    assert (report.added, report.updated, report.removed) == (0, 1, 0)
    assert report.chunks_embedded == len(embedder.seen) == len(index.chunks_of("repos/svc-a1/docs/api.md"))
    assert all("gadgets" in text for text in embedder.seen)
    texts = " ".join(c["text"] for c in index.chunks_of("repos/svc-a1/docs/api.md"))
    assert "gadgets" in texts and "widgets" not in texts


def test_a_new_file_becomes_searchable_with_the_right_service_and_client(index: RetrievalIndex, root: Path) -> None:
    index.sync(root)
    write_text(root / "repos" / "svc-a1" / "docs" / "runbook-new.md", "# New runbook\n\n## Steps\nrestart the widget cache\n")

    report = index.sync(root)

    assert (report.added, report.updated, report.removed) == (1, 0, 0)
    chunk = index.chunks_of("repos/svc-a1/docs/runbook-new.md")[0]
    assert (chunk["metadata"]["service"], chunk["metadata"]["application"], chunk["metadata"]["client"]) == (
        "svc-a1", "app-a1", "client-a")


def test_a_deleted_file_leaves_the_index(index: RetrievalIndex, root: Path) -> None:
    # A document created from the chat is not listed in any manifest, so deleting it is consistent data.
    extra = root / "repos" / "svc-b1" / "docs" / "extra.md"
    write_text(extra, "# Extra\n\n## Notes\nsome notes about safety\n")
    index.sync(root)
    assert index.chunks_of("repos/svc-b1/docs/extra.md")

    extra.unlink()
    report = index.sync(root)

    assert (report.added, report.updated, report.removed) == (0, 0, 1)
    assert index.chunks_of("repos/svc-b1/docs/extra.md") == []
    assert "repos/svc-b1/docs/extra.md" not in index.stored_versions()


def test_sync_stops_with_a_clear_error_when_a_manifest_lists_a_deleted_document(
    index: RetrievalIndex, root: Path
) -> None:
    index.sync(root)
    (root / "repos" / "svc-b1" / "README.md").unlink()  # still listed by repos/svc-b1/service.yaml

    with pytest.raises(GraphBuildError) as exc:
        index.sync(root)

    assert "repos/svc-b1/service.yaml" in str(exc.value) and "README.md" in str(exc.value)
    assert "repos/svc-b1/README.md" in index.stored_versions()  # nothing was half-applied


def test_a_document_marked_obsolete_changes_status(index: RetrievalIndex, root: Path, tmp_path: Path) -> None:
    index.sync(root)
    assert {c["metadata"]["status"] for c in index.chunks_of("repos/svc-a1/docs/api.md")} == {"current"}
    workspace = Workspace(root=root, audit_file=tmp_path / "audit.jsonl")
    set_obsolete(workspace, "svc-a1", "docs/api.md", "Replaced by v2", None)

    report = index.sync(root)

    assert (report.added, report.updated, report.removed) == (0, 1, 0)
    assert {c["metadata"]["status"] for c in index.chunks_of("repos/svc-a1/docs/api.md")} == {"obsolete"}
    assert all("status: obsolete" not in c["text"] for c in index.chunks_of("repos/svc-a1/docs/api.md"))


def test_a_service_that_moves_to_another_application_is_noticed_without_a_file_change(
    index: RetrievalIndex, root: Path
) -> None:
    index.sync(root)
    assert index.chunks_of("repos/svc-a2/README.md")[0]["metadata"]["application"] == "app-a2"
    edit(root / "repos" / "svc-a2" / "service.yaml", lambda m: m.update(application="app-a1"))

    report = index.sync(root)

    assert report.updated >= 1
    assert index.chunks_of("repos/svc-a2/README.md")[0]["metadata"]["application"] == "app-a1"


def test_a_document_that_loses_all_its_text_is_removed_from_the_index(index: RetrievalIndex, root: Path) -> None:
    index.sync(root)
    (root / "repos" / "svc-b1" / "README.md").write_text("# svc-b1\n", encoding="utf-8")

    report = index.sync(root)

    assert report.updated == 1
    assert index.chunks_of("repos/svc-b1/README.md") == []
    assert report.to_dict()["empty"] >= 1


def test_the_report_is_plain_data(index: RetrievalIndex, root: Path) -> None:
    data = index.sync(root).to_dict()
    assert set(data) == {"added", "updated", "removed", "unchanged", "empty", "chunks_embedded"}
    assert all(isinstance(v, int) for v in data.values())
