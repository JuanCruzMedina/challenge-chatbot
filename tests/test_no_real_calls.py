"""Spec: automated tests cannot spend money."""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import anthropic
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_a_real_client_created_in_the_suite_cannot_reach_the_api() -> None:
    assert os.environ["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:9"
    client = anthropic.Anthropic(api_key="sk-ant-not-real", max_retries=0, timeout=5)

    with pytest.raises(anthropic.APIConnectionError):
        client.messages.create(model="claude-haiku-5-5", max_tokens=8, messages=[{"role": "user", "content": "x"}])


def test_the_developers_key_provider_and_cap_cannot_leak_into_the_suite(tmp_path: Path) -> None:
    """Run a probe test in a child pytest whose environment has a key, a provider and a model set."""
    probe = tmp_path / "test_probe.py"
    probe.write_text(textwrap.dedent("""
        import os

        def test_probe():
            for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "LLM_PROVIDER", "ANTHROPIC_MODEL",
                         "ANTHROPIC_MAX_USD", "LIVE_LLM"):
                assert name not in os.environ, name
            assert os.environ["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:9"
            assert "cost_ledger" in os.environ["ANTHROPIC_LEDGER"]
    """), encoding="utf-8")
    shutil_conftest = ROOT / "tests" / "conftest.py"
    (tmp_path / "conftest.py").write_text(shutil_conftest.read_text(encoding="utf-8"), encoding="utf-8")
    env = {**os.environ, "ANTHROPIC_API_KEY": "sk-ant-leak", "ANTHROPIC_AUTH_TOKEN": "leak", "LLM_PROVIDER": "anthropic",
           "ANTHROPIC_MODEL": "claude-opus-5-5", "ANTHROPIC_MAX_USD": "99", "LIVE_LLM": "1"}

    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(probe)],
                            cwd=tmp_path, env=env, capture_output=True, text=True)

    assert result.returncode == 0, result.stdout + result.stderr
