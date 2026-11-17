"""scripts/seed_workspace.py: prepares a complete, writable copy of the sample ecosystem (add-agent design.md D-6)."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

from ecosystem_assistant.knowledge.graph.build import build_graph
from tests.data.helpers import load_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE = REPO_ROOT / "data" / "ecosystem"
ENTRIES = ("README.md", "company.yaml", "company", "clients", "repos", "prs")


def _load_seed_module():
    spec = importlib.util.spec_from_file_location("seed_workspace", REPO_ROOT / "scripts" / "seed_workspace.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _digest(root: Path, ignore: tuple[str, ...] = ()) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name not in ignore
    }


def test_seed_copies_the_whole_ecosystem(tmp_path: Path) -> None:
    seed = _load_seed_module().seed
    dest = tmp_path / "ws"

    seed(SAMPLE, dest)

    assert _digest(dest, ignore=(".seeded-workspace",)) == _digest(SAMPLE)
    assert {p.name for p in dest.iterdir()} == set(ENTRIES) | {".seeded-workspace"}
    expected_services = {p.name for p in (SAMPLE / "repos").iterdir() if p.is_dir()}
    assert len(expected_services) >= 7
    assert {p.name for p in (dest / "repos").iterdir()} == expected_services


def test_the_seeded_workspace_is_a_valid_data_root_for_the_validator_and_the_graph(tmp_path: Path) -> None:
    dest = tmp_path / "ws"
    _load_seed_module().seed(SAMPLE, dest)

    assert load_validator().validate(dest).errors == []
    assert build_graph(dest).nodes("service")


def test_seeding_again_restores_a_fresh_copy_of_every_known_entry(tmp_path: Path) -> None:
    seed = _load_seed_module().seed
    dest = tmp_path / "ws"
    seed(SAMPLE, dest)
    (dest / "repos" / "payments-service" / "docs" / "api-v1.md").write_text("tampered", encoding="utf-8")
    (dest / "repos" / "payments-service" / "docs" / "extra.md").write_text("x", encoding="utf-8")
    (dest / "clients" / "demo-grocery" / "product" / "extra.md").write_text("x", encoding="utf-8")
    (dest / "company.yaml").unlink()

    seed(SAMPLE, dest)

    assert _digest(dest, ignore=(".seeded-workspace",)) == _digest(SAMPLE)


def test_seeding_again_leaves_unknown_files_of_the_workspace_alone(tmp_path: Path) -> None:
    seed = _load_seed_module().seed
    dest = tmp_path / "ws"
    seed(SAMPLE, dest)
    (dest / "my-notes.txt").write_text("keep me", encoding="utf-8")

    seed(SAMPLE, dest)

    assert (dest / "my-notes.txt").read_text(encoding="utf-8") == "keep me"


def test_seeding_never_changes_the_sample_data(tmp_path: Path) -> None:
    seed = _load_seed_module().seed
    before = _digest(SAMPLE)
    dest = tmp_path / "ws"
    seed(SAMPLE, dest)
    seed(SAMPLE, dest)
    assert _digest(SAMPLE) == before


@pytest.mark.parametrize("entry", ["repos", "clients", "company.yaml"])
def test_seed_refuses_to_wipe_a_folder_it_did_not_create(tmp_path: Path, entry: str) -> None:
    seed = _load_seed_module().seed
    dest = tmp_path / "precious"
    target = dest / entry
    if entry.endswith(".yaml"):
        dest.mkdir()
        target.write_text("do not delete", encoding="utf-8")
        keep = target
    else:
        target.mkdir(parents=True)
        keep = target / "important.txt"
        keep.write_text("do not delete", encoding="utf-8")

    with pytest.raises(SystemExit):
        seed(SAMPLE, dest)

    assert keep.read_text(encoding="utf-8") == "do not delete"
