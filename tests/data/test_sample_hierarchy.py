"""Spec: the committed sample data has the company, client and application structure."""
from __future__ import annotations

import subprocess
import sys
from collections import Counter

import yaml

from tests.data.helpers import SAMPLE, SCRIPT, load_validator

COMPANY = yaml.safe_load((SAMPLE / "company.yaml").read_text(encoding="utf-8")) if (SAMPLE / "company.yaml").exists() else {}


def _clients() -> dict[str, dict]:
    return {c["id"]: c for c in COMPANY.get("clients", [])}


def test_the_company_has_two_clients_and_three_applications() -> None:
    assert COMPANY["company"]["id"]
    assert set(_clients()) == {"demo-grocery", "demo-logistics"}
    assert {a["id"] for a in COMPANY["applications"]} == {"storefront", "fleet-tracker", "driver-app"}


def test_each_application_belongs_to_exactly_one_known_client() -> None:
    clients = _clients()
    ids = [a["id"] for a in COMPANY["applications"]]
    assert len(ids) == len(set(ids))
    for app in COMPANY["applications"]:
        assert app["client"] in clients


def test_one_client_owns_more_than_one_application() -> None:
    per_client = Counter(a["client"] for a in COMPANY["applications"])
    assert max(per_client.values()) >= 2
    assert per_client["demo-logistics"] == 2 and per_client["demo-grocery"] == 1


def test_every_client_has_an_existing_vision_and_feature_catalog() -> None:
    for client in COMPANY["clients"]:
        assert (SAMPLE / client["vision"]).is_file(), client["id"]
        assert (SAMPLE / client["features"]).is_file(), client["id"]


def test_the_visions_of_the_two_clients_differ() -> None:
    texts = {cid: (SAMPLE / c["vision"]).read_text(encoding="utf-8") for cid, c in _clients().items()}
    assert len(set(texts.values())) == 2
    assert all(len(t.strip()) > 200 for t in texts.values())


def test_the_original_service_folders_are_still_present() -> None:
    folders = {p.name for p in (SAMPLE / "repos").iterdir() if p.is_dir()}
    assert {"catalog-service", "orders-service", "payments-service", "notifications-service"} <= folders
    assert {"tracking-service", "routing-service", "driver-service"} <= folders


def test_services_are_placed_in_the_expected_applications() -> None:
    placement = {}
    for manifest in (SAMPLE / "repos").glob("*/service.yaml"):
        data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        placement[data["name"]] = (data["client"], data["application"])
    assert placement == {
        "catalog-service": ("demo-grocery", "storefront"),
        "orders-service": ("demo-grocery", "storefront"),
        "payments-service": ("demo-grocery", "storefront"),
        "notifications-service": ("demo-grocery", "storefront"),
        "tracking-service": ("demo-logistics", "fleet-tracker"),
        "routing-service": ("demo-logistics", "fleet-tracker"),
        "driver-service": ("demo-logistics", "driver-app"),
    }


def test_the_pr_101_replacement_manifest_carries_client_and_application() -> None:
    manifest = yaml.safe_load(
        (SAMPLE / "prs" / "pr-101-payments-api-v2" / "files" / "service.yaml").read_text(encoding="utf-8")
    )
    assert (manifest["client"], manifest["application"]) == ("demo-grocery", "storefront")


def test_the_whole_committed_data_validates() -> None:
    result = load_validator().validate(SAMPLE)
    assert result.errors == []
    assert any("DEPRECATED" in line and "orders-service" in line for line in result.summary)


def test_the_command_line_lists_each_client_with_its_applications_and_services() -> None:
    out = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False)
    lines = out.stdout.splitlines()
    assert out.returncode == 0, out.stdout
    assert any(line.startswith("Company: ") for line in lines)
    assert "  Client: Demo Grocery (demo-grocery)" in lines
    assert "  Client: Demo Logistics (demo-logistics)" in lines
    assert any(
        line.startswith("    Application: ") and "(fleet-tracker)" in line
        and "routing-service" in line and "tracking-service" in line
        for line in lines
    )
