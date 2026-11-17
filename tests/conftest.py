"""Every automated test runs with the Anthropic API unreachable and the developer's settings removed.

A real call would spend money. So the API address points at a discard port that nothing listens on, the key, the
token, the provider and the model chosen in the developer's shell (or in a `.env` loaded by a tool) are removed, and
the spending ledger is written inside the test's temporary folder.
"""
from __future__ import annotations

from pathlib import Path

import pytest

UNROUTABLE = "http://127.0.0.1:9"
REMOVED = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE", "LLM_PROVIDER", "ANTHROPIC_MODEL",
           "ANTHROPIC_MAX_USD", "LIVE_LLM")


@pytest.fixture(autouse=True)
def no_real_model_calls(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    for name in REMOVED:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", UNROUTABLE)
    monkeypatch.setenv("ANTHROPIC_LEDGER", str(tmp_path_factory.mktemp("ledger") / "cost_ledger.json"))
