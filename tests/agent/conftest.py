from __future__ import annotations

import asyncio
import shutil
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, TypeVar

import pytest

from tests.data.helpers import SAMPLE

T = TypeVar("T")


def run(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async scenario from a synchronous test."""
    return asyncio.run(coro)


@pytest.fixture
def workspace_dir(tmp_path: Path) -> Path:
    """A writable, complete copy of the sample ecosystem (what scripts/seed_workspace.py makes)."""
    target = tmp_path / "workspace"
    shutil.copytree(SAMPLE, target)
    return target


@pytest.fixture
def audit_file(tmp_path: Path) -> Path:
    return tmp_path / "audit" / "actions.jsonl"
