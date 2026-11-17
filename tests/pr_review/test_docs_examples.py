"""The example in docs/pr-review.md runs as written and prints what the document says."""
from __future__ import annotations

import contextlib
import io
import re
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[2] / "docs" / "pr-review.md"
REPO_ROOT = DOC.parents[1]
PAIR = re.compile(r"```python\n(.*?)```\s*\n\s*```text\n(.*?)```", re.DOTALL)


def test_every_documented_example_prints_its_documented_output(monkeypatch: pytest.MonkeyPatch) -> None:
    pairs = PAIR.findall(DOC.read_text(encoding="utf-8"))
    assert pairs, "the document should keep its worked example"
    monkeypatch.chdir(REPO_ROOT)
    namespace: dict[str, object] = {}
    for code, expected in pairs:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(compile(code, str(DOC), "exec"), namespace)  # noqa: S102 - our own documentation
        assert out.getvalue().strip() == expected.strip(), f"documented output differs for:\n{code}"


def test_the_document_covers_what_a_reader_needs() -> None:
    text = DOC.read_text(encoding="utf-8")
    for needle in ("--dry-run", "pr.yaml", "Measured with", "Limits", "not installed", "untrusted", "eval_pr_review.py"):
        assert needle in text, needle
