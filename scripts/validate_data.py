"""Validate the consistency of the sample data (an invented ecosystem).

Usage: uv run --no-project --with pyyaml python scripts/validate_data.py
Exits with code 1 if there are errors.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent / "data" / "ecosystem"
REQUIRED = [
    "name", "repo", "owner_team", "tech_lead", "lifecycle", "description",
    "provides_apis", "consumes_apis", "publishes_events", "subscribes_events",
    "docs", "features",
]


def load(path: Path):
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def as_list(base):
    return base if isinstance(base, list) else [base]


def exists(base, rel: str) -> bool:
    return any((b / rel).exists() for b in as_list(base))


def check(services: dict, features: dict, label: str, errors: list, warnings: list):
    """Check cross references. `services` maps name -> (manifest, folder or list of folders)."""
    feat_ids = {f["id"] for f in features["features"]}
    epic_ids = {e["id"] for e in features["epics"]}
    provided: dict = {}
    published: dict = {}
    subscribed: dict = {}

    for name, (m, base) in services.items():
        for key in REQUIRED:
            if key not in m:
                errors.append(f"[{label}] {name}: missing key '{key}'")
        for doc in m.get("docs", []):
            if not exists(base, doc):
                errors.append(f"[{label}] {name}: missing doc '{doc}'")
        for api in m.get("provides_apis", []):
            provided.setdefault(api["id"], []).append((name, api))
            if "doc" in api and not exists(base, api["doc"]):
                errors.append(f"[{label}] {name}: missing API doc '{api['doc']}'")
        for ev in m.get("publishes_events", []):
            published.setdefault(ev, []).append(name)
        for ev in m.get("subscribes_events", []):
            subscribed.setdefault(ev, []).append(name)
        for fid in m.get("features", []):
            if fid not in feat_ids:
                errors.append(f"[{label}] {name}: unknown feature '{fid}'")

    for name, (m, _) in services.items():
        for api_id in m.get("consumes_apis", []):
            if api_id not in provided:
                errors.append(f"[{label}] {name}: consumes an API nobody provides '{api_id}'")
    for ev, subs in subscribed.items():
        if ev not in published:
            errors.append(f"[{label}] event '{ev}' is consumed by {subs} but nobody publishes it")
    for ev, pubs in published.items():
        if ev not in subscribed:
            warnings.append(f"[{label}] event '{ev}' is published by {pubs} with no consumers")

    # Two-way consistency between services and features
    for f in features["features"]:
        if f["epic"] not in epic_ids:
            errors.append(f"[{label}] {f['id']}: unknown epic '{f['epic']}'")
        for svc in f["services"]:
            if svc not in services:
                errors.append(f"[{label}] {f['id']}: unknown service '{svc}'")
            elif f["id"] not in services[svc][0].get("features", []):
                errors.append(f"[{label}] {f['id']} lists {svc}, but {svc} does not declare that feature")
    for name, (m, _) in services.items():
        for fid in m.get("features", []):
            f = next((x for x in features["features"] if x["id"] == fid), None)
            if f and name not in f["services"]:
                errors.append(f"[{label}] {name} declares {fid}, but the feature does not list the service")
    return provided


def main() -> int:
    errors: list = []
    warnings: list = []
    features = load(ROOT / "product" / "features.yaml")
    if not (ROOT / "product" / "product-vision.md").exists():
        errors.append("missing product/product-vision.md")

    services = {}
    for manifest in sorted((ROOT / "repos").glob("*/service.yaml")):
        m = load(manifest)
        services[m["name"]] = (m, manifest.parent)
    check(services, features, "base", errors, warnings)
    print(f"Base services: {', '.join(services)}")

    # State after each simulated PR
    for pr_dir in sorted((ROOT / "prs").glob("pr-*")):
        pr = load(pr_dir / "pr.yaml")
        for ch in pr["changes"]:
            if not (pr_dir / "files" / ch["path"]).exists():
                errors.append(f"[{pr['id']}] change '{ch['path']}' is missing from files/")
        after = dict(services)
        overlay = pr_dir / "files" / "service.yaml"
        if overlay.exists():
            m = load(overlay)
            # New docs live in the PR folder; existing ones live in the base repo.
            after[m["name"]] = (m, [pr_dir / "files", services[m["name"]][1]])
        provided = check(after, features, pr["id"], errors, warnings)
        print(f"{pr['id']}: {pr['title']}")
        for api_id, entries in provided.items():
            for _svc, api in entries:
                if api.get("status") == "deprecated":
                    users = [n for n, (m, _) in after.items() if api_id in m.get("consumes_apis", [])]
                    print(f"  {api_id} {api['version']} DEPRECATED (sunset {api.get('sunset')}); "
                          f"affected consumers: {', '.join(users) or 'none'}")

    for w in warnings:
        print("WARNING:", w)
    for e in errors:
        print("ERROR:", e)
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
