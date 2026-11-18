"""Spec: the answer exposes the document passages it retrieved (expose-passages-in-knowledge-tool)."""
from __future__ import annotations

from pathlib import Path

from ecosystem_assistant.knowledge.flow.answer import MAX_PASSAGE_CHARS, passage_info
from ecosystem_assistant.knowledge.flow.evidence import Passage
from ecosystem_assistant.knowledge.retrieval.chunking import chunk_document
from ecosystem_assistant.knowledge.retrieval.documents import discover_documents
from tests.data.helpers import SAMPLE
from tests.flow.test_flow import EMPTY_PLAN, flow

QUESTION = "What should I do when a vehicle disappears from the map?"


def test_passages_come_with_the_answer(sample_graph, sample_index) -> None:
    f, _ = flow(sample_graph, sample_index, [EMPTY_PLAN, {"answer": "see the runbook [D1]", "citations": ["D1"]}])

    answer = f.ask(QUESTION)

    assert answer.passages, "the retrieved passages must travel with the answer"
    first = answer.passages[0]
    assert first.id == "D1" and first.path.endswith(".md") and first.heading_path and first.text
    assert not first.text.startswith(first.heading_path), "the text is the section body, not the heading path"
    assert [p.id for p in answer.passages] == [f"D{n}" for n in range(1, len(answer.passages) + 1)]
    assert "passages" in answer.to_dict()


def test_every_passage_of_the_sample_data_is_an_exact_piece_of_its_file() -> None:
    checked = 0
    for relative in discover_documents(SAMPLE):
        raw = (Path(SAMPLE) / relative).read_text(encoding="utf-8")
        for chunk in chunk_document(relative, raw):
            passage = Passage("D1", chunk.text, 1.0, chunk.path, chunk.heading_path, chunk.title, "", "", chunk.status)
            info = passage_info(passage, raw)
            assert info.exact is True and info.text in raw, (relative, chunk.heading_path)
            checked += 1
    assert checked > 30


def test_a_text_that_is_not_in_the_file_is_marked_not_exact() -> None:
    passage = Passage("D1", "Title\n\nline one\n\nline two", 1.0, "a.md", "Title", "Title", "", "", "current")
    info = passage_info(passage, "# Title\r\n\r\nline one\r\n\r\nline two\r\n")  # a file with Windows line endings
    assert info.exact is False


def test_a_long_passage_is_cut_and_marked_truncated() -> None:
    body = "x" * (MAX_PASSAGE_CHARS + 500)
    passage = Passage("D2", f"Title\n\n{body}", 1.0, "a.md", "Title", "Title", "", "", "current")

    info = passage_info(passage, f"# Title\n\n{body}\n")

    assert info.truncated is True and len(info.text) == MAX_PASSAGE_CHARS
    assert info.exact is False  # a cut text must never be presented as a safe quote


def _info(path: str):
    passage = Passage("D1", "Heading\n\nbody", 1.0, path, "Heading", "T", "", "", "current")
    return passage_info(passage, "Heading\n\nbody")


def test_a_service_passage_names_its_service_and_the_path_inside_it() -> None:
    info = _info("repos/driver-service/README.md")
    assert (info.service, info.doc_path) == ("driver-service", "README.md")
    assert info.to_dict()["service"] == "driver-service"

    nested = _info("repos/payments-service/docs/api-v1.md")
    assert (nested.service, nested.doc_path) == ("payments-service", "docs/api-v1.md")


def test_a_passage_outside_a_service_has_no_service() -> None:
    info = _info("clients/demo-grocery/product/vision.md")
    assert (info.service, info.doc_path) == ("", "")
