"""The validator is callable as a function on any data root (spec: callable on any data root)."""
from __future__ import annotations

import shutil
from pathlib import Path

from tests.data.helpers import SAMPLE, load_validator


def test_validate_returns_errors_warnings_and_summary_for_the_committed_data() -> None:
    result = load_validator().validate(SAMPLE)
    assert result.errors == []
    assert any("DEPRECATED" in line and "orders-service" in line for line in result.summary)


def test_validate_works_on_a_modified_copy_without_touching_the_original(tmp_path: Path) -> None:
    validator = load_validator()
    copy = tmp_path / "ecosystem"
    shutil.copytree(SAMPLE, copy)
    (copy / "repos" / "orders-service" / "docs" / "api.md").unlink()

    broken = validator.validate(copy)
    original = validator.validate(SAMPLE)

    assert any("orders-service" in e and "api.md" in e for e in broken.errors)
    assert original.errors == []
