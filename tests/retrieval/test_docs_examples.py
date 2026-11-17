"""The examples in docs/retrieval-index.md run as written and print what the document says."""
from __future__ import annotations

import contextlib
import io
import re
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[2] / "docs" / "retrieval-index.md"
REPO_ROOT = DOC.parents[1]
# A ```python block immediately followed by a ```text block with its expected output.
PAIR = re.compile(r"```python\n(.*?)```\s*\n\s*```text\n(.*?)```", re.DOTALL)


def test_every_documented_example_prints_its_documented_output(monkeypatch: pytest.MonkeyPatch) -> None:
    pairs = PAIR.findall(DOC.read_text(encoding="utf-8"))
    assert len(pairs) >= 4, "the document should keep its worked examples"

    monkeypatch.chdir(REPO_ROOT)  # the examples use the relative path data/ecosystem
    monkeypatch.setenv("EMBEDDER", "hashing")
    namespace: dict[str, object] = {}  # examples build on each other, like a notebook
    for code, expected in pairs:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(compile(code, str(DOC), "exec"), namespace)  # noqa: S102 - our own documentation
        assert out.getvalue().strip() == expected.strip(), f"documented output differs for:\n{code}"


def test_the_document_states_the_numbers_that_the_evaluation_set_can_reproduce() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "19 of 22" in text and "20 of 22" in text
    assert text.count("\n") > 50
    for needle in ("ALLOW_MODEL_DOWNLOAD=1", "VECTOR_INDEX_DIR", "include_obsolete", "No relevance threshold"):
        assert needle in text, needle
