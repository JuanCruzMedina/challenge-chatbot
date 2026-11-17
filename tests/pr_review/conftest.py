from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.data.helpers import SAMPLE


@pytest.fixture
def workspace_dir(tmp_path: Path) -> Path:
    target = tmp_path / "workspace"
    shutil.copytree(SAMPLE, target)
    return target
