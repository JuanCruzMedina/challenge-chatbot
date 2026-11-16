"""Spec: ecosystem-data-hierarchy rules, exercised on a synthetic dataset (one mutation per rule)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.data.fixture import build_dataset, edit
from tests.data.helpers import load_validator


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return build_dataset(tmp_path / "ecosystem")


def errors_for(root: Path) -> list[str]:
    return load_validator().validate(root).errors


def has_error(errors: list[str], *needles: str) -> bool:
    return any(all(n in e for n in needles) for e in errors)


# --- a consistent dataset ------------------------------------------------------------

def test_a_consistent_dataset_passes(root: Path) -> None:
    result = load_validator().validate(root)
    assert result.errors == []


# --- service client / application ------------------------------------------------------

def test_an_unknown_application_is_rejected(root: Path) -> None:
    edit(root / "repos" / "svc-b1" / "service.yaml", lambda m: m.update(application="ghost-app"))
    assert has_error(errors_for(root), "svc-b1", "ghost-app")


def test_an_application_of_another_client_is_rejected(root: Path) -> None:
    edit(root / "repos" / "svc-a2" / "service.yaml", lambda m: m.update(application="app-b1"))
    assert has_error(errors_for(root), "svc-a2", "client-a", "app-b1")


@pytest.mark.parametrize("key", ["client", "application"])
def test_a_missing_client_or_application_is_rejected(root: Path, key: str) -> None:
    edit(root / "repos" / "svc-b1" / "service.yaml", lambda m: m.pop(key))
    assert has_error(errors_for(root), "svc-b1", f"missing key '{key}'")


def test_an_unknown_client_is_rejected(root: Path) -> None:
    edit(root / "repos" / "svc-b1" / "service.yaml", lambda m: m.update(client="ghost-client"))
    assert has_error(errors_for(root), "svc-b1", "ghost-client")


def test_a_duplicate_service_name_is_rejected(root: Path) -> None:
    shutil.copytree(root / "repos" / "svc-b1", root / "repos" / "svc-b1-copy")
    assert has_error(errors_for(root), "duplicate", "svc-b1")


def test_a_manifest_name_that_differs_from_its_folder_is_rejected(root: Path) -> None:
    edit(root / "repos" / "svc-a1" / "service.yaml", lambda m: m.update(name="svc-a-one"))
    assert has_error(errors_for(root), "svc-a1", "svc-a-one")


# --- per-client product vision --------------------------------------------------------

def test_a_missing_vision_is_rejected(root: Path) -> None:
    (root / "clients" / "client-b" / "product" / "vision.md").unlink()
    assert has_error(errors_for(root), "client-b", "vision.md")


def test_a_missing_feature_catalog_is_rejected(root: Path) -> None:
    (root / "clients" / "client-b" / "product" / "features.yaml").unlink()
    assert has_error(errors_for(root), "client-b", "features.yaml")


def test_a_feature_pointing_at_another_clients_service_is_rejected(root: Path) -> None:
    edit(
        root / "clients" / "client-a" / "product" / "features.yaml",
        lambda d: d["features"][0]["services"].append("svc-b1"),
    )
    assert has_error(errors_for(root), "A-FEAT-1", "svc-b1", "client-a", "client-b")


# --- company-wide uniqueness -----------------------------------------------------------

def test_a_feature_id_repeated_by_two_clients_is_rejected(root: Path) -> None:
    edit(
        root / "clients" / "client-b" / "product" / "features.yaml",
        lambda d: d["features"][0].update(id="A-FEAT-1"),
    )
    assert has_error(errors_for(root), "A-FEAT-1", "client-a", "client-b")


def test_an_epic_id_repeated_by_two_clients_is_rejected(root: Path) -> None:
    edit(
        root / "clients" / "client-b" / "product" / "features.yaml",
        lambda d: (d["epics"][0].update(id="A-EPIC-1"), d["features"][0].update(epic="A-EPIC-1")),
    )
    assert has_error(errors_for(root), "A-EPIC-1", "client-a", "client-b")


def test_an_api_id_provided_by_two_services_is_rejected(root: Path) -> None:
    edit(
        root / "repos" / "svc-b1" / "service.yaml",
        lambda m: m.update(provides_apis=[{"id": "a1-api", "version": "v1", "status": "active"}]),
    )
    assert has_error(errors_for(root), "a1-api", "svc-a1", "svc-b1")


# --- simulated PRs ---------------------------------------------------------------------

@pytest.mark.parametrize("key", ["client", "application"])
def test_a_pr_manifest_without_client_or_application_is_rejected(root: Path, key: str) -> None:
    edit(root / "prs" / "pr-1" / "files" / "service.yaml", lambda m: m.pop(key))
    assert has_error(errors_for(root), "PR-1", "svc-a1", f"missing key '{key}'")


def test_a_pr_manifest_with_another_clients_application_is_rejected(root: Path) -> None:
    edit(root / "prs" / "pr-1" / "files" / "service.yaml", lambda m: m.update(application="app-b1"))
    assert has_error(errors_for(root), "PR-1", "svc-a1", "app-b1")


# --- summary ---------------------------------------------------------------------------

def test_the_command_line_output_lists_clients_applications_and_services(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = load_validator().main([str(root)])
    lines = capsys.readouterr().out.splitlines()

    assert code == 0
    assert "Company: Demo Studio (demo-studio)" in lines
    assert "  Client: Client A (client-a)" in lines
    assert "    Application: App A1 (app-a1): svc-a1" in lines
    assert "    Application: App A2 (app-a2): svc-a2" in lines
    assert "  Client: Client B (client-b)" in lines
    assert "    Application: App B1 (app-b1): svc-b1" in lines
    assert lines.index("  Client: Client A (client-a)") < lines.index("    Application: App A1 (app-a1): svc-a1")


def test_the_summary_is_also_returned_by_the_function(root: Path) -> None:
    summary = load_validator().validate(root).summary
    assert "    Application: App A1 (app-a1): svc-a1" in summary
