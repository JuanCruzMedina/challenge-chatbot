"""Validate the consistency of the sample data (an invented ecosystem).

Usage: uv run python scripts/validate_data.py [data-root]
Exits with code 1 if there are errors. ``validate(root)`` can be called on any data root.

Layout checked (see data/ecosystem/README.md):
  company.yaml                              company, clients and applications
  clients/<client>/product/...              each client's product vision and feature catalog
  repos/<service>/service.yaml + docs       one folder per service, names unique company-wide
  prs/<pr>/pr.yaml + files/                 simulated PRs (replacement manifests and new docs)
"""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "data" / "ecosystem"
REQUIRED = [
    "name", "repo", "owner_team", "tech_lead", "lifecycle", "description", "client", "application",
    "provides_apis", "consumes_apis", "publishes_events", "subscribes_events",
    "docs", "features",
]


@dataclass
class Result:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)


def load(path: Path):
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def as_list(base):
    return base if isinstance(base, list) else [base]


def exists(base, rel: str) -> bool:
    return any((b / rel).exists() for b in as_list(base))


# --- company file and per-client product data ------------------------------------------

@dataclass
class Company:
    data: dict
    clients: dict  # id -> client entry
    apps: dict     # id -> application entry
    features: dict # merged {"epics": [...], "features": [...]} across clients
    feature_client: dict  # feature id -> client id


def load_company(root: Path, errors: list) -> Company | None:
    path = root / "company.yaml"
    if not path.exists():
        errors.append("missing company.yaml")
        return None
    data = load(path)
    clients: dict = {}
    for c in data.get("clients", []):
        for key in ("id", "name", "vision", "features"):
            if key not in c:
                errors.append(f"company.yaml: client {c.get('id', '?')!r} is missing '{key}'")
        if c.get("id") in clients:
            errors.append(f"company.yaml: duplicate client id '{c['id']}'")
        clients[c.get("id")] = c
    apps: dict = {}
    for a in data.get("applications", []):
        for key in ("id", "name", "client"):
            if key not in a:
                errors.append(f"company.yaml: application {a.get('id', '?')!r} is missing '{key}'")
        if a.get("id") in apps:
            errors.append(f"company.yaml: duplicate application id '{a['id']}'")
        if a.get("client") not in clients:
            errors.append(f"company.yaml: application '{a.get('id')}' belongs to unknown client '{a.get('client')}'")
        apps[a.get("id")] = a

    merged = {"epics": [], "features": []}
    feature_client: dict = {}
    epic_client: dict = {}
    for cid, c in clients.items():
        if "vision" in c and not (root / c["vision"]).exists():
            errors.append(f"client '{cid}': missing vision file {c['vision']}")
        if "features" not in c:
            continue
        catalog = root / c["features"]
        if not catalog.exists():
            errors.append(f"client '{cid}': missing feature catalog {c['features']}")
            continue
        content = load(catalog)
        for epic in content.get("epics", []):
            if epic["id"] in epic_client:
                errors.append(f"duplicate epic id '{epic['id']}' declared by clients "
                              f"{epic_client[epic['id']]} and {cid}")
            epic_client.setdefault(epic["id"], cid)
            merged["epics"].append(epic)
        for feat in content.get("features", []):
            if feat["id"] in feature_client:
                errors.append(f"duplicate feature id '{feat['id']}' declared by clients "
                              f"{feature_client[feat['id']]} and {cid}")
            feature_client.setdefault(feat["id"], cid)
            merged["features"].append(feat)
    return Company(data, clients, apps, merged, feature_client)


def check_hierarchy(services: dict, company: Company, label: str, errors: list) -> None:
    """Every service sits in a known application of a known client, and features stay inside one client."""
    for name, (m, _) in services.items():
        client, app = m.get("client"), m.get("application")
        if client is not None and client not in company.clients:
            errors.append(f"[{label}] {name}: unknown client '{client}'")
        if app is not None and app not in company.apps:
            errors.append(f"[{label}] {name}: unknown application '{app}'")
        if client in company.clients and app in company.apps and company.apps[app].get("client") != client:
            errors.append(f"[{label}] {name}: application '{app}' belongs to client "
                          f"'{company.apps[app].get('client')}', not '{client}'")

    for feat in company.features["features"]:
        owner = company.feature_client.get(feat["id"])
        for svc in feat["services"]:
            if svc in services and services[svc][0].get("client") not in (None, owner):
                errors.append(f"[{label}] feature {feat['id']} of client '{owner}' lists service "
                              f"'{svc}' of client '{services[svc][0].get('client')}'")


# --- cross references --------------------------------------------------------------------

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

    for api_id, entries in provided.items():
        providers = sorted({svc for svc, _ in entries})
        if len(providers) > 1:
            errors.append(f"[{label}] API id '{api_id}' is provided by more than one service: {', '.join(providers)}")
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


def hierarchy_summary(company: Company, services: dict) -> list[str]:
    c = company.data.get("company", {})
    lines = [f"Company: {c.get('name', '?')} ({c.get('id', '?')})"]
    for cid, client in company.clients.items():
        lines.append(f"  Client: {client.get('name', '?')} ({cid})")
        for aid, app in company.apps.items():
            if app.get("client") != cid:
                continue
            names = sorted(n for n, (m, _) in services.items() if m.get("application") == aid)
            lines.append(f"    Application: {app.get('name', '?')} ({aid}): {', '.join(names) or '(no services)'}")
    return lines


# --- entry points ------------------------------------------------------------------------

def validate(root: Path = DEFAULT_ROOT) -> Result:
    result = Result()
    company = load_company(root, result.errors)
    if company is None:
        return result

    # Collect manifests in a list first, then report duplicates and mismatches, then index by name.
    manifests = [(load(path), path.parent) for path in sorted((root / "repos").glob("*/service.yaml"))]
    counts = Counter(m.get("name") for m, _ in manifests)
    for name, n in counts.items():
        if n > 1:
            folders = ", ".join(f"repos/{f.name}" for m, f in manifests if m.get("name") == name)
            result.errors.append(f"duplicate service name '{name}' declared in {folders}")
    for m, folder in manifests:
        if m.get("name") != folder.name:
            result.errors.append(f"service folder 'repos/{folder.name}' declares name '{m.get('name')}'; "
                                 f"the manifest name must equal the folder name")
    services = {m["name"]: (m, folder) for m, folder in manifests}

    check(services, company.features, "base", result.errors, result.warnings)
    check_hierarchy(services, company, "base", result.errors)
    result.summary.extend(hierarchy_summary(company, services))
    result.summary.append(f"Base services: {', '.join(services)}")

    # State after each simulated PR
    for pr_dir in sorted((root / "prs").glob("pr-*")):
        pr = load(pr_dir / "pr.yaml")
        for ch in pr["changes"]:
            if not (pr_dir / "files" / ch["path"]).exists():
                result.errors.append(f"[{pr['id']}] change '{ch['path']}' is missing from files/")
        after = dict(services)
        overlay = pr_dir / "files" / "service.yaml"
        if overlay.exists():
            m = load(overlay)
            # New docs live in the PR folder; existing ones live in the base repo.
            folders = [pr_dir / "files"] + ([services[m["name"]][1]] if m["name"] in services else [])
            after[m["name"]] = (m, folders)
        provided = check(after, company.features, pr["id"], result.errors, result.warnings)
        check_hierarchy(after, company, pr["id"], result.errors)
        result.summary.append(f"{pr['id']}: {pr['title']}")
        for api_id, entries in provided.items():
            for _svc, api in entries:
                if api.get("status") == "deprecated":
                    users = [n for n, (m, _) in after.items() if api_id in m.get("consumes_apis", [])]
                    result.summary.append(
                        f"  {api_id} {api['version']} DEPRECATED (sunset {api.get('sunset')}); "
                        f"affected consumers: {', '.join(users) or 'none'}"
                    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    result = validate(Path(args[0]) if args else DEFAULT_ROOT)
    for line in result.summary:
        print(line)
    for w in result.warnings:
        print("WARNING:", w)
    for e in result.errors:
        print("ERROR:", e)
    print("OK" if not result.errors else f"{len(result.errors)} error(s)")
    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
