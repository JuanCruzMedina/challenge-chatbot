"""Spec: documents are split into described chunks (one chunk per section)."""
from __future__ import annotations

import hashlib

from ecosystem_assistant.knowledge.retrieval.chunking import MAX_CHARS, chunk_document

THREE_SECTIONS = """# Orders API

## Endpoints
alpha endpoint text

## Charges
beta charge text

## Rules
gamma rule text
"""


def test_a_document_becomes_one_chunk_per_section() -> None:
    chunks = chunk_document("repos/x/docs/api.md", THREE_SECTIONS)

    assert [c.heading_path for c in chunks] == ["Orders API > Endpoints", "Orders API > Charges", "Orders API > Rules"]
    first = chunks[0]
    assert first.text.startswith("Orders API > Endpoints")
    assert "alpha endpoint text" in first.text
    assert "beta" not in first.text and "gamma" not in first.text
    assert all(c.title == "Orders API" for c in chunks)


def test_a_small_document_is_a_single_chunk() -> None:
    chunks = chunk_document("repos/x/README.md", "# Only heading\n\nA few lines.\nAnd one more.\n")
    assert len(chunks) == 1
    assert chunks[0].heading_path == "Only heading"
    assert "A few lines." in chunks[0].text


def test_nested_headings_extend_the_heading_path() -> None:
    chunks = chunk_document("p.md", "# T\n\n## A\ntext a\n\n### A1\ntext a1\n\n## B\ntext b\n")
    assert [c.heading_path for c in chunks] == ["T > A", "T > A > A1", "T > B"]


def test_a_heading_with_no_text_of_its_own_yields_no_chunk() -> None:
    chunks = chunk_document("p.md", "# T\n\n## Empty\n\n## Full\nsome text\n")
    assert [c.heading_path for c in chunks] == ["T > Full"]


def test_a_document_without_headings_uses_the_file_name_as_title() -> None:
    chunks = chunk_document("repos/x/docs/notes.md", "just text, no heading\n")
    assert len(chunks) == 1 and chunks[0].title == "notes"


def _paragraph(label: str, size: int = 400) -> str:
    text = (f"{label} " + "word " * (size // 5 + 1))[:size].strip()
    assert len(text) >= size - 5  # the helper must really produce the requested size
    return text


def test_a_long_section_is_split_at_paragraph_boundaries() -> None:
    paragraphs = [_paragraph(f"para{i}") for i in range(5)]  # ~2000 characters in total
    document = "# T\n\n## Long\n" + "\n\n".join(paragraphs) + "\n"

    chunks = chunk_document("p.md", document)

    assert len(chunks) >= 2
    assert all(len(c.body) <= MAX_CHARS for c in chunks)
    rejoined = [p for c in chunks for p in c.body.split("\n\n")]
    assert rejoined == paragraphs  # none cut, none lost, order kept
    assert {c.heading_path for c in chunks} == {"T > Long"}


def test_a_single_paragraph_longer_than_the_limit_stays_whole() -> None:
    giant = _paragraph("giant", 2000)
    chunks = chunk_document("p.md", f"# T\n\n## S\n{giant}\n\nshort tail\n")

    bodies = [c.body for c in chunks]
    assert giant in bodies
    assert any("short tail" in b for b in bodies)


def test_hash_lines_inside_fenced_code_are_not_headings() -> None:
    document = "# T\n\n## Setup\nrun this:\n\n```bash\n# not a heading\necho hi\n\necho again\n```\n\nafter\n"
    chunks = chunk_document("p.md", document)

    assert [c.heading_path for c in chunks] == ["T > Setup"]
    assert "# not a heading\necho hi\n\necho again" in chunks[0].body  # the block was not split


def test_front_matter_is_removed_from_the_text_and_its_status_is_read() -> None:
    obsolete = '---\nstatus: obsolete\nobsolete_reason: "Replaced by v2"\nreplaced_by: "docs/api-v2.md"\n---\n# API v1\n\n## Rules\nold rules\n'
    chunks = chunk_document("p.md", obsolete)

    assert [c.status for c in chunks] == ["obsolete"]
    assert all("status: obsolete" not in c.text and "---" not in c.text for c in chunks)
    assert chunks[0].title == "API v1"
    assert chunk_document("p.md", THREE_SECTIONS)[0].status == "current"


def test_ids_texts_and_hash_are_deterministic() -> None:
    first = chunk_document("repos/x/docs/api.md", THREE_SECTIONS)
    second = chunk_document("repos/x/docs/api.md", THREE_SECTIONS)

    assert [c.id for c in first] == ["repos/x/docs/api.md#0", "repos/x/docs/api.md#1", "repos/x/docs/api.md#2"]
    assert [(c.id, c.text) for c in first] == [(c.id, c.text) for c in second]
    expected_hash = hashlib.sha256(THREE_SECTIONS.encode("utf-8")).hexdigest()
    assert {c.content_hash for c in first} == {expected_hash}
