from __future__ import annotations

from pathlib import Path

import pytest

from tests.data.fixture import build_dataset


@pytest.fixture
def fx_root(tmp_path: Path) -> Path:
    """The small synthetic dataset (company, two clients, three applications, three services)."""
    return build_dataset(tmp_path / "synthetic")
