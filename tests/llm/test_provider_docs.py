"""The documentation of the Anthropic provider names variables and commands that exist."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = (ROOT / "docs" / "agent.md").read_text(encoding="utf-8")
SOURCE = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "src").rglob("*.py"))


def test_every_anthropic_variable_in_the_document_is_read_by_the_code() -> None:
    section = DOC.split("## Using Claude instead of the local model")[1].split("## The routing evaluation")[0]
    variables = set(re.findall(r"`((?:ANTHROPIC|LLM)_[A-Z_]+)`", section))
    assert {"LLM_PROVIDER", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_MAX_USD", "ANTHROPIC_LEDGER"} <= variables
    for name in variables:
        assert name in SOURCE, f"{name} is documented but no code reads it"


def test_the_documented_live_check_command_is_the_scripts_own_usage() -> None:
    assert "LIVE_LLM=1 uv run python scripts/live_check.py --yes" in DOC
    script = (ROOT / "scripts" / "live_check.py").read_text(encoding="utf-8")
    assert "LIVE_LLM=1 uv run python scripts/live_check.py --yes" in script


def test_the_default_cap_and_model_in_the_document_match_the_code() -> None:
    from ecosystem_assistant.llm.ledger import DEFAULT_CAP_USD
    from ecosystem_assistant.llm.pricing import DEFAULT_MODEL

    assert f"| `ANTHROPIC_MAX_USD` | `{DEFAULT_CAP_USD}` |" in DOC
    assert f"| `ANTHROPIC_MODEL` | `{DEFAULT_MODEL}` |" in DOC
