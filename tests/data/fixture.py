"""Builds a minimal, valid, hierarchical dataset in a temporary folder.

Company ``demo-studio`` with clients ``client-a`` (applications ``app-a1``, ``app-a2``) and
``client-b`` (application ``app-b1``). Tests mutate a copy of it to trigger one rule at a time.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def dump(path: Path, data: Any) -> None:
    write_text(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def edit(path: Path, change: Callable[[Any], None]) -> None:
    """Load a YAML file, let ``change`` mutate it in place, and write it back."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data)
    dump(path, data)


def manifest(name: str, client: str, application: str, **overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": name,
        "repo": f"demo/{name}",
        "owner_team": f"{name}-team",
        "tech_lead": "Test Lead",
        "lifecycle": "production",
        "description": f"Invented service {name}.",
        "client": client,
        "application": application,
        "provides_apis": [],
        "consumes_apis": [],
        "publishes_events": [],
        "subscribes_events": [],
        "docs": ["README.md"],
        "features": [],
    }
    data.update(overrides)
    return data


def build_dataset(root: Path) -> Path:
    dump(
        root / "company.yaml",
        {
            "company": {"id": "demo-studio", "name": "Demo Studio"},
            "clients": [
                {
                    "id": cid,
                    "name": f"Client {cid[-1].upper()}",
                    "vision": f"clients/{cid}/product/vision.md",
                    "features": f"clients/{cid}/product/features.yaml",
                }
                for cid in ("client-a", "client-b")
            ],
            "applications": [
                {"id": "app-a1", "name": "App A1", "client": "client-a"},
                {"id": "app-a2", "name": "App A2", "client": "client-a"},
                {"id": "app-b1", "name": "App B1", "client": "client-b"},
            ],
        },
    )
    write_text(root / "company" / "overview.md", "# Demo Studio\n\nTwo invented clients.\n")

    for cid, vision in (("client-a", "Client A wants speed."), ("client-b", "Client B wants safety.")):
        write_text(root / "clients" / cid / "product" / "vision.md", f"# Vision {cid}\n\n{vision}\n")
    dump(
        root / "clients" / "client-a" / "product" / "features.yaml",
        {
            "epics": [{"id": "A-EPIC-1", "name": "Epic A", "product_owner": "PO A"}],
            "features": [
                {"id": "A-FEAT-1", "name": "Feature A", "epic": "A-EPIC-1", "status": "released",
                 "services": ["svc-a1", "svc-a2"]}
            ],
        },
    )
    dump(
        root / "clients" / "client-b" / "product" / "features.yaml",
        {
            "epics": [{"id": "B-EPIC-1", "name": "Epic B", "product_owner": "PO B"}],
            "features": [
                {"id": "B-FEAT-1", "name": "Feature B", "epic": "B-EPIC-1", "status": "released",
                 "services": ["svc-b1"]}
            ],
        },
    )

    services = {
        "svc-a1": manifest(
            "svc-a1", "client-a", "app-a1",
            provides_apis=[{"id": "a1-api", "version": "v1", "status": "active", "doc": "docs/api.md"}],
            publishes_events=["a.event"],
            docs=["README.md", "docs/api.md"],
            features=["A-FEAT-1"],
        ),
        "svc-a2": manifest(
            "svc-a2", "client-a", "app-a2",
            consumes_apis=["a1-api"], subscribes_events=["a.event"], features=["A-FEAT-1"],
        ),
        "svc-b1": manifest("svc-b1", "client-b", "app-b1", features=["B-FEAT-1"]),
    }
    for name, data in services.items():
        base = root / "repos" / name
        dump(base / "service.yaml", data)
        write_text(base / "README.md", f"# {name}\n")
    write_text(root / "repos" / "svc-a1" / "docs" / "api.md", "# a1-api\n")

    pr = root / "prs" / "pr-1"
    dump(
        pr / "pr.yaml",
        {"id": "PR-1", "repo": "demo/svc-a1", "title": "Touch svc-a1 manifest", "author": "Test",
         "merged_at": "2026-01-01", "description": "x",
         "changes": [{"path": "service.yaml", "status": "modified"}]},
    )
    dump(pr / "files" / "service.yaml", {**services["svc-a1"], "description": "Changed by PR-1."})
    return root
