"""The knowledge graph and its query interface (design.md D-1, D-7 to D-9).

Only this package touches NetworkX. Everything that leaves it is plain data: results are small
dataclasses with ``to_dict()``, they list the source files of the facts they report, and an entity
that cannot be found yields a :class:`NotFound` result instead of an exception.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from collections import deque
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

import networkx as nx

from ecosystem_assistant.knowledge.graph import model as m

_TOKEN = re.compile(r"[a-z0-9]+")
_TECHNICAL = frozenset({m.PROVIDES, m.CONSUMES, m.PUBLISHES, m.SUBSCRIBES_TO})
_TYPE_ALIASES = {"people": "person", "persons": "person"}
MATCH_LABELS = ("exact", "tokens", "partial", "substring")


def _fold(text: str) -> str:
    """Lowercase and remove accents, so ``Tomás`` and ``tomas`` compare equal."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(_fold(text))


# --- results (plain data) -----------------------------------------------------------------

class _Plain:
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)  # type: ignore[call-overload]


@dataclass(frozen=True)
class EntityRef(_Plain):
    id: str
    type: str
    name: str


@dataclass(frozen=True)
class Candidate(_Plain):
    id: str
    type: str
    name: str
    match: str  # one of MATCH_LABELS


@dataclass
class NotFound(_Plain):
    query: str
    message: str
    suggestions: list[EntityRef] = field(default_factory=list)
    expected_type: str | None = None
    found: bool = False


@dataclass
class AppServices(_Plain):
    application: EntityRef
    services: list[EntityRef]


@dataclass
class ClientOverview(_Plain):
    client: EntityRef
    applications: list[AppServices]
    vision: EntityRef | None
    sources: list[str]
    found: bool = True


@dataclass
class ApplicationServices(_Plain):
    application: EntityRef
    client: EntityRef | None
    services: list[EntityRef]
    sources: list[str]
    found: bool = True


@dataclass
class ServiceOwner(_Plain):
    service: EntityRef
    team: EntityRef | None
    lead: EntityRef | None
    sources: list[str]
    found: bool = True


@dataclass
class Provider(_Plain):
    service: EntityRef
    versions: list[dict[str, Any]]


@dataclass
class Consumer(_Plain):
    service: EntityRef
    application: EntityRef | None
    client: EntityRef | None


@dataclass
class DeprecatedVersion(_Plain):
    provider: EntityRef
    version: str
    sunset: str | None


@dataclass
class ApiConsumers(_Plain):
    api: EntityRef
    providers: list[Provider]
    consumers: list[Consumer]
    deprecated: list[DeprecatedVersion]
    sources: list[str]
    found: bool = True


@dataclass
class EventFlow(_Plain):
    event: EntityRef
    publishers: list[EntityRef]
    subscribers: list[EntityRef]
    sources: list[str]
    found: bool = True


@dataclass
class FeatureInfo(_Plain):
    feature: EntityRef
    epic: EntityRef | None
    status: str


@dataclass
class DocumentInfo(_Plain):
    document: EntityRef
    title: str
    path: str


@dataclass
class ProductContext(_Plain):
    service: EntityRef
    application: EntityRef | None
    client: EntityRef | None
    features: list[FeatureInfo]
    vision: DocumentInfo | None
    sources: list[str]
    found: bool = True


@dataclass
class PathStep(_Plain):
    source: EntityRef
    relation: str
    direction: str  # "out": the relation points from source to target; "in": from target to source
    target: EntityRef


@dataclass
class RelationPath(_Plain):
    start: EntityRef
    end: EntityRef
    connected: bool
    steps: list[PathStep]
    sources: list[str]
    found: bool = True


@dataclass
class RelationGroup(_Plain):
    relation: str
    direction: str
    entities: list[EntityRef]


@dataclass
class Description(_Plain):
    entity: EntityRef
    attributes: dict[str, Any]
    relations: list[RelationGroup]
    sources: list[str]
    found: bool = True


@dataclass
class ObsoleteDoc(_Plain):
    document: EntityRef
    service: str | None
    path: str
    reason: str | None
    replaced_by: str | None


@dataclass
class ObsoleteDocuments(_Plain):
    documents: list[ObsoleteDoc]
    sources: list[str]
    found: bool = True


@dataclass
class EntityList(_Plain):
    type: str
    entities: list[EntityRef]
    sources: list[str]
    found: bool = True


@dataclass
class TeamService(_Plain):
    service: EntityRef
    lead: EntityRef | None


@dataclass
class TeamOverview(_Plain):
    team: EntityRef
    services: list[TeamService]
    sources: list[str]
    found: bool = True


# --- the graph ----------------------------------------------------------------------------

class KnowledgeGraph:
    """An immutable view of the ecosystem graph. Build it with ``build_graph(root)``."""

    def __init__(self, graph: nx.MultiDiGraph) -> None:
        self._g = graph

    # --- plain-data inspection ------------------------------------------------------------

    def nodes(self, entity_type: str | None = None) -> list[dict[str, Any]]:
        """Every entity (optionally of one type) as ``{id, type, name, sources, attributes}``, sorted by id."""
        items = [
            {"id": key, "type": d["type"], "name": d["name"], "sources": list(d["sources"]),
             "attributes": dict(d["attributes"])}
            for key, d in self._g.nodes(data=True)
            if entity_type is None or d["type"] == entity_type
        ]
        return sorted(items, key=lambda n: n["id"])

    def edges(self, relation: str | None = None) -> list[dict[str, Any]]:
        """Every relation (optionally of one kind) as ``{source, target, relation, sources, attributes}``."""
        items = [
            {"source": u, "target": v, "relation": rel, "sources": list(d["sources"]),
             "attributes": {k: (list(x) if isinstance(x, list) else x) for k, x in d["attributes"].items()}}
            for u, v, rel, d in self._g.edges(keys=True, data=True)
            if relation is None or rel == relation
        ]
        return sorted(items, key=lambda e: (e["source"], e["target"], e["relation"]))

    def export(self) -> dict[str, list[dict[str, Any]]]:
        """The whole graph as plain data; two builds of the same data export equal values."""
        return {"nodes": self.nodes(), "edges": self.edges()}

    # --- finding entities -------------------------------------------------------------------

    def find_entities(self, text: str, type: str | None = None, limit: int = 10) -> list[Candidate]:  # noqa: A002
        """Entities matching ``text`` in loose form, best match first. An empty list when nothing matches."""
        q_tokens = _tokens(text)
        if not q_tokens:
            return []
        raw = _fold(text).strip()
        q_joined = " ".join(q_tokens)
        q_set = set(q_tokens)

        scored: list[tuple[int, int, str, str]] = []
        for key, data in self._g.nodes(data=True):
            if type is not None and data["type"] != type:
                continue
            best: int | None = None
            for label in (data["name"], m.split_key(key)[1]):
                tokens = _tokens(label)
                joined = " ".join(tokens)
                if _fold(label).strip() == raw:
                    score = 0
                elif joined == q_joined:
                    score = 1
                elif q_set <= set(tokens):
                    score = 2
                elif q_joined in joined:
                    score = 3
                else:
                    continue
                best = score if best is None else min(best, score)
            if best is not None:
                scored.append((best, m.TYPE_ORDER.index(data["type"]), data["name"], key))
        scored.sort()
        return [
            Candidate(id=key, type=self._g.nodes[key]["type"], name=name, match=MATCH_LABELS[score])
            for score, _order, name, key in scored[:limit]
        ]

    def _ref(self, key: str) -> EntityRef:
        data = self._g.nodes[key]
        return EntityRef(id=key, type=data["type"], name=data["name"])

    def _resolve(self, text: str, expected: str | None = None) -> str | NotFound:
        if text in self._g and (expected is None or self._g.nodes[text]["type"] == expected):
            return text
        candidates = self.find_entities(text, type=expected, limit=1)
        if candidates:
            return candidates[0].id
        return self._not_found(text, expected)

    def _not_found(self, text: str, expected: str | None) -> NotFound:
        labels: dict[str, list[str]] = {}
        for key, data in self._g.nodes(data=True):
            if expected is None or data["type"] == expected:
                labels.setdefault(" ".join(_tokens(data["name"])), []).append(key)
        # Closest label first (difflib orders them by similarity); within one label, by type.
        close = difflib.get_close_matches(" ".join(_tokens(text)), list(labels), n=3, cutoff=0.5)
        keys: list[str] = []
        for label in close:
            for k in sorted(labels[label], key=lambda k: (m.TYPE_ORDER.index(self._g.nodes[k]["type"]), k)):
                if k not in keys:
                    keys.append(k)
        wanted = f"{expected} " if expected else ""
        return NotFound(
            query=text,
            message=f"No {wanted}entity found for {text!r}." + (" Did you mean one of the suggestions?" if keys else ""),
            suggestions=[self._ref(k) for k in keys[:3]],
            expected_type=expected,
        )

    # --- helpers over the graph ---------------------------------------------------------------

    def _targets(self, key: str, relation: str) -> list[str]:
        return sorted(v for _u, v, r in self._g.out_edges(key, keys=True) if r == relation)

    def _origins(self, key: str, relation: str) -> list[str]:
        return sorted(u for u, _v, r in self._g.in_edges(key, keys=True) if r == relation)

    def _first(self, keys: list[str]) -> str | None:
        return keys[0] if keys else None

    def _opt_ref(self, key: str | None) -> EntityRef | None:
        return self._ref(key) if key else None

    def _sources(self, nodes: Iterable[str], edges: Iterable[tuple[str, str, str]] = ()) -> list[str]:
        found: set[str] = set()
        for key in nodes:
            found.update(self._g.nodes[key]["sources"])
        for u, v, rel in edges:
            found.update(self._g.edges[u, v, rel]["sources"])
        return sorted(found)

    def _application_and_client(self, service: str) -> tuple[str | None, str | None]:
        app = self._first(self._origins(service, m.HAS_SERVICE))
        client = self._first(self._origins(app, m.HAS_APPLICATION)) if app else None
        return app, client

    # --- structural questions -------------------------------------------------------------------

    def client_overview(self, client: str) -> ClientOverview | NotFound:
        key = self._resolve(client, m.CLIENT)
        if isinstance(key, NotFound):
            return key
        nodes, edges = {key}, set()
        apps: list[AppServices] = []
        for app in self._targets(key, m.HAS_APPLICATION):
            edges.add((key, app, m.HAS_APPLICATION))
            services = self._targets(app, m.HAS_SERVICE)
            edges.update((app, s, m.HAS_SERVICE) for s in services)
            nodes.update([app, *services])
            apps.append(AppServices(self._ref(app), [self._ref(s) for s in services]))
        vision = self._first(self._targets(key, m.HAS_VISION))
        if vision:
            nodes.add(vision)
            edges.add((key, vision, m.HAS_VISION))
        return ClientOverview(self._ref(key), apps, self._opt_ref(vision), self._sources(nodes, edges))

    def application_services(self, application: str) -> ApplicationServices | NotFound:
        key = self._resolve(application, m.APPLICATION)
        if isinstance(key, NotFound):
            return key
        client = self._first(self._origins(key, m.HAS_APPLICATION))
        services = self._targets(key, m.HAS_SERVICE)
        nodes = {key, *services, *([client] if client else [])}
        edges = {(key, s, m.HAS_SERVICE) for s in services}
        if client:
            edges.add((client, key, m.HAS_APPLICATION))
        return ApplicationServices(
            self._ref(key), self._opt_ref(client), [self._ref(s) for s in services], self._sources(nodes, edges)
        )

    def service_owner(self, service: str) -> ServiceOwner | NotFound:
        key = self._resolve(service, m.SERVICE)
        if isinstance(key, NotFound):
            return key
        team = self._first(self._targets(key, m.OWNED_BY))
        lead = self._first(self._targets(key, m.LED_BY))
        nodes = {key, *[k for k in (team, lead) if k]}
        edges = {(key, k, rel) for k, rel in ((team, m.OWNED_BY), (lead, m.LED_BY)) if k}
        return ServiceOwner(self._ref(key), self._opt_ref(team), self._opt_ref(lead), self._sources(nodes, edges))

    def list_entities(self, type: str) -> EntityList | NotFound:  # noqa: A002
        """Every entity of one type (``team``, ``person``, ``service``, ...), sorted by name."""
        wanted = _fold(type).strip()
        wanted = _TYPE_ALIASES.get(wanted, wanted)
        valid = sorted(m.TYPE_ORDER)
        entity_type = next((t for t in valid if t in (wanted, wanted.removesuffix("s"))), None)
        if entity_type is None:
            return NotFound(
                query=type,
                message=f"Unknown entity type {type!r}. Valid types: {', '.join(valid)}.",
                suggestions=[EntityRef(t, "type", t) for t in valid],
            )
        keys = sorted(
            (k for k, d in self._g.nodes(data=True) if d["type"] == entity_type),
            key=lambda k: (_fold(self._g.nodes[k]["name"]), k),
        )
        return EntityList(entity_type, [self._ref(k) for k in keys], self._sources(keys))

    def team_overview(self, team: str) -> TeamOverview | NotFound:
        """A team, the services it owns and the person who leads each of them."""
        key = self._resolve(team, m.TEAM)
        if isinstance(key, NotFound):
            return key
        nodes, edges = {key}, set()
        services: list[TeamService] = []
        for service in self._origins(key, m.OWNED_BY):
            lead = self._first(self._targets(service, m.LED_BY))
            nodes.add(service)
            edges.add((service, key, m.OWNED_BY))
            if lead:
                nodes.add(lead)
                edges.add((service, lead, m.LED_BY))
            services.append(TeamService(self._ref(service), self._opt_ref(lead)))
        return TeamOverview(self._ref(key), services, self._sources(nodes, edges))

    def api_consumers(self, api: str) -> ApiConsumers | NotFound:
        key = self._resolve(api, m.API)
        if isinstance(key, NotFound):
            return key
        nodes, edges = {key}, set()
        providers: list[Provider] = []
        deprecated: list[DeprecatedVersion] = []
        for service in self._origins(key, m.PROVIDES):
            versions = self._g.edges[service, key, m.PROVIDES]["attributes"].get("versions", [])
            providers.append(Provider(self._ref(service), [dict(v) for v in versions]))
            deprecated += [
                DeprecatedVersion(self._ref(service), v["version"], v.get("sunset"))
                for v in versions if v.get("status") == "deprecated"
            ]
            nodes.add(service)
            edges.add((service, key, m.PROVIDES))
        consumers: list[Consumer] = []
        for service in self._origins(key, m.CONSUMES):
            app, client = self._application_and_client(service)
            consumers.append(Consumer(self._ref(service), self._opt_ref(app), self._opt_ref(client)))
            nodes.update(k for k in (service, app, client) if k)
            edges.add((service, key, m.CONSUMES))
            if app:
                edges.add((app, service, m.HAS_SERVICE))
            if app and client:
                edges.add((client, app, m.HAS_APPLICATION))
        return ApiConsumers(self._ref(key), providers, consumers, deprecated, self._sources(nodes, edges))

    def event_flow(self, event: str) -> EventFlow | NotFound:
        key = self._resolve(event, m.EVENT)
        if isinstance(key, NotFound):
            return key
        publishers = self._origins(key, m.PUBLISHES)
        subscribers = self._origins(key, m.SUBSCRIBES_TO)
        edges = {(s, key, m.PUBLISHES) for s in publishers} | {(s, key, m.SUBSCRIBES_TO) for s in subscribers}
        return EventFlow(
            self._ref(key), [self._ref(s) for s in publishers], [self._ref(s) for s in subscribers],
            self._sources({key, *publishers, *subscribers}, edges),
        )

    def service_product_context(self, service: str) -> ProductContext | NotFound:
        key = self._resolve(service, m.SERVICE)
        if isinstance(key, NotFound):
            return key
        app, client = self._application_and_client(key)
        nodes, edges = {key}, set()
        features: list[FeatureInfo] = []
        for feature in self._targets(key, m.IMPLEMENTS):
            epic = self._first(self._targets(feature, m.PART_OF))
            features.append(FeatureInfo(
                self._ref(feature), self._opt_ref(epic), self._g.nodes[feature]["attributes"].get("status", "")
            ))
            nodes.update(k for k in (feature, epic) if k)
            edges.add((key, feature, m.IMPLEMENTS))
            if epic:
                edges.add((feature, epic, m.PART_OF))
        vision: DocumentInfo | None = None
        if client:
            nodes.add(client)
            doc = self._first(self._targets(client, m.HAS_VISION))
            if doc:
                attrs = self._g.nodes[doc]["attributes"]
                vision = DocumentInfo(self._ref(doc), attrs.get("title", ""), attrs.get("path", ""))
                nodes.add(doc)
                edges.add((client, doc, m.HAS_VISION))
        return ProductContext(
            self._ref(key), self._opt_ref(app), self._opt_ref(client), features, vision,
            self._sources(nodes, edges),
        )

    def relation_path(self, start: str, end: str) -> RelationPath | NotFound:
        a = self._resolve(start)
        if isinstance(a, NotFound):
            return a
        b = self._resolve(end)
        if isinstance(b, NotFound):
            return b

        previous: dict[str, tuple[str, str, str] | None] = {a: None}
        queue = deque([a])
        while queue and b not in previous:
            current = queue.popleft()
            for rel, neighbour, direction in self._neighbours(current):
                if neighbour not in previous:
                    previous[neighbour] = (current, rel, direction)
                    queue.append(neighbour)

        if b not in previous:
            return RelationPath(self._ref(a), self._ref(b), False, [], self._sources([a, b]))
        steps: list[PathStep] = []
        node = b
        while previous[node] is not None:
            parent, rel, direction = previous[node]  # type: ignore[misc]
            steps.append(PathStep(self._ref(parent), rel, direction, self._ref(node)))
            node = parent
        steps.reverse()
        nodes = {a, b, *[s.source.id for s in steps], *[s.target.id for s in steps]}
        edges = {(s.source.id, s.target.id, s.relation) if s.direction == "out" else (s.target.id, s.source.id, s.relation)
                 for s in steps}
        return RelationPath(self._ref(a), self._ref(b), True, steps, self._sources(nodes, edges))

    def _neighbours(self, key: str) -> list[tuple[str, str, str]]:
        """Neighbours as ``(relation, node, direction)``; technical relations are tried first (design D-9)."""
        items = [(r, v, "out") for _u, v, r in self._g.out_edges(key, keys=True)]
        items += [(r, u, "in") for u, _v, r in self._g.in_edges(key, keys=True)]
        items = [i for i in items if i[0] not in m.PATH_EXCLUDED_RELATIONS]
        return sorted(items, key=lambda i: (i[0] not in _TECHNICAL, i[0], i[1], i[2]))

    def describe(self, entity: str) -> Description | NotFound:
        key = self._resolve(entity)
        if isinstance(key, NotFound):
            return key
        groups: dict[tuple[str, str], list[str]] = {}
        edges: set[tuple[str, str, str]] = set()
        for u, v, rel in self._g.out_edges(key, keys=True):
            groups.setdefault((rel, "out"), []).append(v)
            edges.add((u, v, rel))
        for u, v, rel in self._g.in_edges(key, keys=True):
            groups.setdefault((rel, "in"), []).append(u)
            edges.add((u, v, rel))
        relations = [
            RelationGroup(rel, direction, [self._ref(k) for k in sorted(set(keys))])
            for (rel, direction), keys in sorted(groups.items())
        ]
        related = {k for keys in groups.values() for k in keys}
        return Description(
            self._ref(key), dict(self._g.nodes[key]["attributes"]), relations,
            self._sources({key, *related}, edges),
        )

    def obsolete_documents(self) -> ObsoleteDocuments:
        documents: list[ObsoleteDoc] = []
        nodes: set[str] = set()
        for key, data in sorted(self._g.nodes(data=True)):
            if data["type"] != m.DOCUMENT or data["attributes"].get("status") != "obsolete":
                continue
            attrs = data["attributes"]
            owner = self._first(self._origins(key, m.DOCUMENTED_BY))
            service = self._g.nodes[owner]["name"] if owner else None
            doc_id = m.split_key(key)[1]
            path = doc_id[len(service) + 1:] if service else doc_id
            documents.append(ObsoleteDoc(self._ref(key), service, path, attrs.get("obsolete_reason"), attrs.get("replaced_by")))
            nodes.add(key)
        return ObsoleteDocuments(documents, self._sources(nodes))
