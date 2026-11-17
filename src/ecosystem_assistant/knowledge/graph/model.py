"""Vocabulary of the knowledge graph: entity types, relation names and node keys (design.md D-1, D-2)."""
from __future__ import annotations

# Entity types.
COMPANY, CLIENT, APPLICATION, SERVICE = "company", "client", "application", "service"
TEAM, PERSON, API, EVENT = "team", "person", "api", "event"
EPIC, FEATURE, DOCUMENT = "epic", "feature", "document"

# Order used to break ties when ranking entities of different types.
TYPE_ORDER = (SERVICE, API, EVENT, APPLICATION, CLIENT, TEAM, PERSON, FEATURE, EPIC, DOCUMENT, COMPANY)

# Relations (directed, source -> target).
HAS_CLIENT = "HAS_CLIENT"              # company -> client
HAS_APPLICATION = "HAS_APPLICATION"    # client -> application
HAS_SERVICE = "HAS_SERVICE"            # application -> service
OWNED_BY = "OWNED_BY"                  # service -> team
LED_BY = "LED_BY"                      # service -> person
PROVIDES = "PROVIDES"                  # service -> api (edge attribute: versions)
CONSUMES = "CONSUMES"                  # service -> api
PUBLISHES = "PUBLISHES"                # service -> event
SUBSCRIBES_TO = "SUBSCRIBES_TO"        # service -> event
DOCUMENTED_BY = "DOCUMENTED_BY"        # service -> document
IMPLEMENTS = "IMPLEMENTS"              # service -> feature
PART_OF = "PART_OF"                    # feature -> epic
BELONGS_TO = "BELONGS_TO"              # epic -> client
HAS_VISION = "HAS_VISION"              # client -> document

RELATIONS = (
    HAS_CLIENT, HAS_APPLICATION, HAS_SERVICE, OWNED_BY, LED_BY, PROVIDES, CONSUMES,
    PUBLISHES, SUBSCRIBES_TO, DOCUMENTED_BY, IMPLEMENTS, PART_OF, BELONGS_TO, HAS_VISION,
)

# Relations ignored when looking for a connection between two entities: belonging to the same
# company says nothing about how two things are related (design.md D-9).
PATH_EXCLUDED_RELATIONS = frozenset({HAS_CLIENT})

_PREFIX = {DOCUMENT: "doc"}
_TYPE_OF_PREFIX = {v: k for k, v in _PREFIX.items()}


def key(entity_type: str, entity_id: str) -> str:
    """Node key, for example ``service:orders-service`` or ``doc:orders-service/docs/api.md``."""
    return f"{_PREFIX.get(entity_type, entity_type)}:{entity_id}"


def split_key(node_key: str) -> tuple[str, str]:
    """Inverse of :func:`key`: ``(entity_type, entity_id)``."""
    prefix, _, entity_id = node_key.partition(":")
    return _TYPE_OF_PREFIX.get(prefix, prefix), entity_id
