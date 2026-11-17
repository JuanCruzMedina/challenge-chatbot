"""The examples in docs/informational-flow.md run as written and print what the document says."""
from __future__ import annotations

import contextlib
import io
import re
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[2] / "docs" / "informational-flow.md"
REPO_ROOT = DOC.parents[1]
# A ```python block immediately followed by a ```text block with its expected output.
PAIR = re.compile(r"```python\n(.*?)```\s*\n\s*```text\n(.*?)```", re.DOTALL)


def test_every_documented_example_prints_its_documented_output(monkeypatch: pytest.MonkeyPatch) -> None:
    pairs = PAIR.findall(DOC.read_text(encoding="utf-8"))
    assert len(pairs) >= 4, "the document should keep its worked examples"

    monkeypatch.chdir(REPO_ROOT)  # the examples use the relative path data/ecosystem
    namespace: dict[str, object] = {}  # examples build on each other, like a notebook
    for code, expected in pairs:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(compile(code, str(DOC), "exec"), namespace)  # noqa: S102 - our own documentation
        assert out.getvalue().strip() == expected.strip(), f"documented output differs for:\n{code}"


def test_the_document_covers_the_decisions_a_reader_needs() -> None:
    text = DOC.read_text(encoding="utf-8")
    for needle in ("insufficient_evidence", "degraded", "grounded", "LLM_PROVIDER", "OLLAMA_MODEL", "ollama serve",
                   "LANGSMITH", "min_score", "Measured with", "scripts/eval_flow.py", "Limits"):
        assert needle in text, needle
