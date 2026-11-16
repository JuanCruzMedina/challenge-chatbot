"""Characterization: what the validator reports on the committed data must not change while refactoring."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_data.py"


def _run() -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False)


def test_the_committed_data_validates_with_exit_zero() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip().endswith("OK")
    assert "ERROR" not in result.stdout


def test_pr_101_deprecates_payments_api_v1_and_affects_orders_service() -> None:
    out = _run().stdout
    assert "PR-101" in out
    assert "payments-api v1 DEPRECATED (sunset 2027-03-31)" in out
    assert "affected consumers: orders-service" in out
