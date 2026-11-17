"""The examples in docs/agent.md run as written and print what the document says."""
from __future__ import annotations

import contextlib
import io
import re
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[2] / "docs" / "agent.md"
REPO_ROOT = DOC.parents[1]
PAIR = re.compile(r"```python\n(.*?)```\s*\n\s*```text\n(.*?)```", re.DOTALL)


def test_every_documented_example_prints_its_documented_output(monkeypatch: pytest.MonkeyPatch) -> None:
    pairs = PAIR.findall(DOC.read_text(encoding="utf-8"))
    assert len(pairs) >= 2, "the document should keep its worked examples"

    monkeypatch.chdir(REPO_ROOT)
    namespace: dict[str, object] = {}  # examples build on each other, like a notebook
    for code, expected in pairs:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(compile(code, str(DOC), "exec"), namespace)  # noqa: S102 - our own documentation
        assert out.getvalue().strip() == expected.strip(), f"documented output differs for:\n{code}"


def test_the_document_covers_what_a_reader_needs() -> None:
    text = DOC.read_text(encoding="utf-8")
    for needle in ("query_knowledge", "AgentModelError", "ollama serve", "AGENT_DATA_ROOT", "OLLAMA_MODEL",
                   "scripts/eval_agent.py", "Measured with", "Limits", "seed_workspace.py"):
        assert needle in text, needle
