"""scripts/seed_workspace.py: prepares the workspace from the committed sample data."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE = REPO_ROOT / "data" / "ecosystem" / "repos"


def _load_seed_module():
    spec = importlib.util.spec_from_file_location("seed_workspace", REPO_ROOT / "scripts" / "seed_workspace.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _digest(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_seed_copies_every_sample_repo(tmp_path: Path) -> None:
    seed = _load_seed_module().seed
    dest = tmp_path / "ws"
    seed(SAMPLE, dest)
    assert _digest(dest / "repos") == _digest(SAMPLE)
    expected = {p.name for p in SAMPLE.iterdir() if p.is_dir()}
    assert len(expected) >= 4
    assert {p.name for p in (dest / "repos").iterdir()} == expected


def test_seeding_again_restores_a_fresh_copy(tmp_path: Path) -> None:
    seed = _load_seed_module().seed
    dest = tmp_path / "ws"
    seed(SAMPLE, dest)
    edited = dest / "repos" / "payments-service" / "docs" / "api-v1.md"
    edited.write_text("tampered", encoding="utf-8")
    (dest / "repos" / "payments-service" / "docs" / "extra.md").write_text("x", encoding="utf-8")

    seed(SAMPLE, dest)

    assert _digest(dest / "repos") == _digest(SAMPLE)


def test_seeding_never_changes_the_sample_data(tmp_path: Path) -> None:
    seed = _load_seed_module().seed
    before = _digest(SAMPLE)
    dest = tmp_path / "ws"
    seed(SAMPLE, dest)
    seed(SAMPLE, dest)
    assert _digest(SAMPLE) == before


def test_seed_refuses_to_wipe_a_folder_it_did_not_create(tmp_path: Path) -> None:
    seed = _load_seed_module().seed
    dest = tmp_path / "precious"
    (dest / "repos").mkdir(parents=True)
    keep = dest / "repos" / "important.txt"
    keep.write_text("do not delete", encoding="utf-8")

    with pytest.raises(SystemExit):
        seed(SAMPLE, dest)

    assert keep.read_text(encoding="utf-8") == "do not delete"
