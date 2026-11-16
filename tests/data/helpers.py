"""Helpers for tests of the sample data and its validator."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE = REPO_ROOT / "data" / "ecosystem"
SCRIPT = REPO_ROOT / "scripts" / "validate_data.py"


def load_validator() -> ModuleType:
    """Import scripts/validate_data.py as a module.

    It is registered in ``sys.modules`` first: dataclasses with deferred annotations look
    their module up there while the class is being created.
    """
    name = "validate_data"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
