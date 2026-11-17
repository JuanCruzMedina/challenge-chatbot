"""The example in docs/chat-ui.md runs as written and prints what the document says."""
from __future__ import annotations

import contextlib
import io
import json
import re
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parents[2] / "docs" / "chat-ui.md"
ROOT = DOC.parents[1]
PAIR = re.compile(r"```python\n(.*?)```\s*\n\s*```text\n(.*?)```", re.DOTALL)


def test_the_documented_session_prints_its_documented_output(monkeypatch: pytest.MonkeyPatch) -> None:
    pairs = PAIR.findall(DOC.read_text(encoding="utf-8"))
    assert pairs, "the document should keep its worked example"
    monkeypatch.chdir(ROOT)
    namespace: dict[str, object] = {}
    for code, expected in pairs:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(compile(code, str(DOC), "exec"), namespace)  # noqa: S102 - our own documentation
        assert out.getvalue().strip() == expected.strip()


def test_the_documented_commands_match_the_project() -> None:
    """The start command, the address and the graph name in the document are those of the project."""
    text = DOC.read_text(encoding="utf-8")
    config = json.loads((ROOT / "langgraph.json").read_text(encoding="utf-8"))
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "uv run langgraph dev" in text and "http://localhost:2024" in text
    assert f"graph ID\n`{next(iter(config['graphs']))}`" in text
    assert "langgraph-cli" in pyproject
    for needle in ("python -m ecosystem_assistant.chat", "seed_workspace.py", "Not verified", "Limits"):
        assert needle in text, needle
