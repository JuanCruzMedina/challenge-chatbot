"""Build the knowledge graph from an ecosystem data root (design.md D-3 to D-6, D-10).

Reads ``company.yaml``, ``repos/*/service.yaml``, the client product catalogs and the document
files. It never writes anything, and a reference that does not resolve raises
:class:`GraphBuildError` naming the file and the missing item.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import networkx as nx
import yaml

from ecosystem_assistant.knowledge.graph import model as m
from ecosystem_assistant.knowledge.graph.queries import KnowledgeGraph

_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)


class GraphBuildError(Exception):
    """The data cannot be turned into a consistent graph."""


def build_graph(root: Path) -> KnowledgeGraph:
    """Build the graph of the data under ``root``. The same data always gives the same graph."""
    return _Builder(Path(root)).build()


class _Builder:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.g: nx.MultiDiGraph = nx.MultiDiGraph()

    # --- small helpers ------------------------------------------------------------------

    def _rel(self, path: Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def _load(self, path: Path, referenced_from: str | None = None) -> Any:
        if not path.is_file():
            origin = f"{referenced_from}: " if referenced_from else ""
            raise GraphBuildError(f"{origin}file '{self._rel(path)}' not found")
        with path.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def _node(self, entity_type: str, entity_id: str, name: str, source: str, **attrs: Any) -> str:
        node_key = m.key(entity_type, entity_id)
        if node_key in self.g:
            data = self.g.nodes[node_key]
            data["sources"] = sorted(set(data["sources"]) | {source})
        else:
            self.g.add_node(node_key, type=entity_type, name=name, sources=[source], attributes=dict(attrs))
        return node_key

    def _edge(self, src: str, dst: str, relation: str, source: str, **attrs: Any) -> None:
        if self.g.has_edge(src, dst, key=relation):
            data = self.g.edges[src, dst, relation]
            data["sources"] = sorted(set(data["sources"]) | {source})
            for name, value in attrs.items():
                if isinstance(value, list):
                    merged = data["attributes"].setdefault(name, [])
                    merged.extend(v for v in value if v not in merged)
                else:
                    data["attributes"][name] = value
        else:
            self.g.add_edge(src, dst, key=relation, sources=[source], attributes=dict(attrs))

    # --- build ----------------------------------------------------------------------------

    def build(self) -> KnowledgeGraph:
        company = self._load(self.root / "company.yaml")
        feature_ids = self._build_company_and_products(company, "company.yaml")
        self._build_services(feature_ids)
        self._build_document_links()
        return KnowledgeGraph(self.g)

    def _build_company_and_products(self, company: dict, src: str) -> set[str]:
        info = company.get("company", {})
        company_key = self._node(m.COMPANY, info["id"], info.get("name", info["id"]), src,
                                 description=info.get("description", ""))
        client_keys: dict[str, str] = {}
        for client in company.get("clients", []):
            ck = self._node(m.CLIENT, client["id"], client.get("name", client["id"]), src)
            client_keys[client["id"]] = ck
            self._edge(company_key, ck, m.HAS_CLIENT, src)
            vision = self.root / client["vision"]
            vision_key = self._document(f"clients/{client['id']}/product/{vision.name}", vision, src)
            self._edge(ck, vision_key, m.HAS_VISION, src)

        for app in company.get("applications", []):
            if app["client"] not in client_keys:
                raise GraphBuildError(f"{src}: application '{app['id']}' belongs to unknown client '{app['client']}'")
            ak = self._node(m.APPLICATION, app["id"], app.get("name", app["id"]), src)
            self._edge(client_keys[app["client"]], ak, m.HAS_APPLICATION, src)

        feature_ids: set[str] = set()
        for client in company.get("clients", []):
            catalog_path = self.root / client["features"]
            catalog = self._load(catalog_path, src)
            catalog_src = self._rel(catalog_path)
            for epic in catalog.get("epics", []):
                ek = self._node(m.EPIC, epic["id"], epic.get("name", epic["id"]), catalog_src,
                                product_owner=epic.get("product_owner", ""))
                self._edge(ek, client_keys[client["id"]], m.BELONGS_TO, catalog_src)
            for feature in catalog.get("features", []):
                fk = self._node(m.FEATURE, feature["id"], feature.get("name", feature["id"]), catalog_src,
                                status=feature.get("status", ""))
                epic_key = m.key(m.EPIC, feature["epic"])
                if epic_key not in self.g:
                    raise GraphBuildError(
                        f"{catalog_src}: feature '{feature['id']}' is part of unknown epic '{feature['epic']}'"
                    )
                self._edge(fk, epic_key, m.PART_OF, catalog_src)
                feature_ids.add(feature["id"])
        return feature_ids

    def _document(self, doc_id: str, path: Path, referenced_from: str) -> str:
        """Create a document entity from its file: first heading as title, front matter as status."""
        if not path.is_file():
            raise GraphBuildError(f"{referenced_from}: document '{self._rel(path)}' not found")
        text = path.read_bytes().decode("utf-8")
        status, extra = "current", {}
        body = text
        front = _FRONT_MATTER.match(text)
        if front:
            meta = yaml.safe_load(front.group(1)) or {}
            if str(meta.get("status", "")).lower() == "obsolete":
                status = "obsolete"
                extra = {k: meta[k] for k in ("obsolete_reason", "replaced_by") if k in meta}
            body = text[front.end():]
        title = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), path.name)
        rel = self._rel(path)
        return self._node(m.DOCUMENT, doc_id, doc_id, rel, title=title, status=status, path=rel, **extra)

    def _build_document_links(self) -> None:
        """Read ``about`` from the front matter of every markdown document of a service, listed in a manifest or not.

        A name that matches no service, API or event is kept in ``unresolved_links`` and never fails the build.
        """
        unresolved: list[dict[str, str]] = []
        for service_dir in sorted(p for p in (self.root / "repos").glob("*") if p.is_dir()):
            service_key = m.key(m.SERVICE, service_dir.name)
            for path in sorted(service_dir.rglob("*.md")):
                relative = path.relative_to(service_dir)
                if any(part.startswith(".") for part in relative.parts):
                    continue
                doc_id = f"{service_dir.name}/{relative.as_posix()}"
                names, problem = self._about(path)
                if problem:
                    unresolved.append({"document": doc_id, "name": problem})
                if not names or service_key not in self.g:
                    continue
                source = self._rel(path)
                doc_key = self._document(doc_id, path, source)
                self._edge(service_key, doc_key, m.DOCUMENTED_BY, source)
                for name in names:
                    target = next((k for k in (m.key(t, name) for t in (m.SERVICE, m.API, m.EVENT)) if k in self.g), None)
                    if target is None:
                        unresolved.append({"document": doc_id, "name": name})
                    else:
                        self._edge(doc_key, target, m.ABOUT, source)
        self.g.graph["unresolved_links"] = unresolved

    @staticmethod
    def _about(path: Path) -> tuple[list[str], str]:
        """The names in the ``about`` field of a document, and a problem text when its front matter cannot be read."""
        front = _FRONT_MATTER.match(path.read_bytes().decode("utf-8", errors="replace"))
        if not front:
            return [], ""
        try:
            meta = yaml.safe_load(front.group(1)) or {}
        except yaml.YAMLError:
            return [], "<front matter could not be read>"
        about = meta.get("about") if isinstance(meta, dict) else None
        items = [about] if isinstance(about, str) else about if isinstance(about, list) else []
        return sorted({str(item).strip() for item in items if str(item).strip()}), ""

    def _build_services(self, feature_ids: set[str]) -> None:
        provided: set[str] = set()
        consumed: list[tuple[str, str, str]] = []  # (manifest source, service, api)

        for manifest_path in sorted((self.root / "repos").glob("*/service.yaml")):
            src = self._rel(manifest_path)
            data = self._load(manifest_path)
            name = data["name"]
            app_key = m.key(m.APPLICATION, data.get("application", ""))
            if app_key not in self.g:
                raise GraphBuildError(
                    f"{src}: service '{name}' declares unknown application '{data.get('application')}'"
                )
            sk = self._node(m.SERVICE, name, name, src, description=data.get("description", ""),
                            lifecycle=data.get("lifecycle", ""), repo=data.get("repo", ""))
            self._edge(app_key, sk, m.HAS_SERVICE, src)
            self._edge(sk, self._node(m.TEAM, data["owner_team"], data["owner_team"], src), m.OWNED_BY, src)
            self._edge(sk, self._node(m.PERSON, data["tech_lead"], data["tech_lead"], src), m.LED_BY, src)

            versions: dict[str, list[dict[str, Any]]] = {}
            for api in data.get("provides_apis", []):
                entry = {"version": api["version"], "status": api["status"]}
                if "sunset" in api:
                    entry["sunset"] = api["sunset"]
                versions.setdefault(api["id"], []).append(entry)
            for api_id, entries in versions.items():
                self._edge(sk, self._node(m.API, api_id, api_id, src), m.PROVIDES, src, versions=entries)
                provided.add(api_id)
            for api_id in data.get("consumes_apis", []):
                consumed.append((src, name, api_id))
            for event in data.get("publishes_events", []):
                self._edge(sk, self._node(m.EVENT, event, event, src), m.PUBLISHES, src)
            for event in data.get("subscribes_events", []):
                self._edge(sk, self._node(m.EVENT, event, event, src), m.SUBSCRIBES_TO, src)
            for doc in data.get("docs", []):
                dk = self._document(f"{name}/{doc}", manifest_path.parent / doc, src)
                self._edge(sk, dk, m.DOCUMENTED_BY, src)
            for feature in data.get("features", []):
                if feature not in feature_ids:
                    raise GraphBuildError(f"{src}: service '{name}' implements unknown feature '{feature}'")
                self._edge(sk, m.key(m.FEATURE, feature), m.IMPLEMENTS, src)

        for src, service, api_id in consumed:
            if api_id not in provided:
                raise GraphBuildError(f"{src}: service '{service}' consumes API '{api_id}' that no service provides")
            self._edge(m.key(m.SERVICE, service), m.key(m.API, api_id), m.CONSUMES, src)
