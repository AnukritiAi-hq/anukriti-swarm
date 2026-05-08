"""Storage backend protocol + in-memory default.

Every MCP service in this package (execution memory, trace store,
provenance, evidence cache) goes through a single ``StorageBackend``
interface. That keeps the services agnostic of where their data
actually lives:

- ``InMemoryBackend``   — default; keeps everything in a dict of lists.
                          Safe for demos, tests, and any environment
                          without MongoDB. Not persistent across
                          processes.
- ``MongoDBBackend``    — lazily imports pymongo and maps each
                          collection to a real MongoDB collection when
                          ``MONGODB_URI`` is set. See ``mongo.py``.

The protocol stays intentionally small: ``insert`` / ``query`` /
``count`` / ``delete`` / ``ping``. Services implement anything fancier
on top (indexes, TTL, search) by composing these primitives.

All values stored MUST be JSON-safe — services call ``_json_safe`` on
their dataclasses before insertion so backends never need to know
about ``datetime``, ``Enum``, or nested models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class StorageBackend(Protocol):
    """Minimal persistence interface every MCP service depends on.

    All methods take / return plain ``dict`` objects so implementations
    can be swapped (e.g. Mongo ↔ in-memory ↔ a test fake) without any
    changes to service code.
    """

    # Informational
    @property
    def mode(self) -> str:
        """Human-readable backend name, e.g. 'in_memory' / 'mongodb_atlas'."""
        ...

    def ping(self) -> bool:
        """Cheap health check. ``True`` means the backend is usable."""
        ...

    # CRUD
    def insert(self, collection: str, doc: dict[str, Any]) -> str:
        """Insert ``doc`` into ``collection`` and return its id."""
        ...

    def query(
        self,
        collection: str,
        filter: dict[str, Any] | None = None,
        *,
        sort: list[tuple[str, int]] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return matching documents. ``sort`` uses (field, 1|-1) pairs."""
        ...

    def count(self, collection: str, filter: dict[str, Any] | None = None) -> int:
        """Count matching documents."""
        ...

    def delete(self, collection: str, filter: dict[str, Any]) -> int:
        """Delete matching documents and return how many were removed."""
        ...


# ---------------------------------------------------------------------------
# In-memory implementation
# ---------------------------------------------------------------------------


@dataclass
class InMemoryBackend:
    """Process-local, list-of-dicts backend.

    This is the default. It keeps one ``list[dict]`` per collection and
    implements ``query`` with simple equality matching on each filter
    key plus a small subset of MongoDB operators that the MCP services
    actually use (``$in``, ``$exists``, ``$gte``, ``$lte``). That is
    intentionally limited — callers who need rich querying should use
    the MongoDB backend, which forwards filters to pymongo verbatim.
    """

    collections: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    # ----- informational --------------------------------------------

    @property
    def mode(self) -> str:
        return "in_memory"

    def ping(self) -> bool:
        return True

    # ----- CRUD -----------------------------------------------------

    def insert(self, collection: str, doc: dict[str, Any]) -> str:
        from uuid import uuid4

        bucket = self.collections.setdefault(collection, [])
        stored = dict(doc)
        stored.setdefault("_id", uuid4().hex)
        bucket.append(stored)
        return stored["_id"]

    def query(
        self,
        collection: str,
        filter: dict[str, Any] | None = None,
        *,
        sort: list[tuple[str, int]] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = list(self.collections.get(collection, ()))

        if filter:
            rows = [r for r in rows if _matches(r, filter)]

        if sort:
            # Compose keys by applying sorts right-to-left (stable sort).
            for field_name, direction in reversed(sort):
                rows.sort(
                    key=lambda r, k=field_name: _sort_key(r.get(k)),
                    reverse=direction < 0,
                )

        if limit is not None:
            rows = rows[:limit]

        return [dict(r) for r in rows]

    def count(self, collection: str, filter: dict[str, Any] | None = None) -> int:
        if not filter:
            return len(self.collections.get(collection, ()))
        return sum(
            1 for r in self.collections.get(collection, ()) if _matches(r, filter)
        )

    def delete(self, collection: str, filter: dict[str, Any]) -> int:
        bucket = self.collections.get(collection, [])
        kept: list[dict[str, Any]] = []
        removed = 0
        for r in bucket:
            if _matches(r, filter):
                removed += 1
            else:
                kept.append(r)
        self.collections[collection] = kept
        return removed


# ---------------------------------------------------------------------------
# Filter / sort helpers
# ---------------------------------------------------------------------------


def _matches(doc: dict[str, Any], filter: dict[str, Any]) -> bool:
    """Minimal subset of MongoDB filter semantics.

    Supported operators:
      - equality:   ``{"gene": "CYP2C19"}``
      - ``$in``:    ``{"population": {"$in": ["SAS","AFR"]}}``
      - ``$exists``: ``{"citations": {"$exists": True}}``
      - ``$gte`` / ``$lte``: numeric bounds

    Any unknown operator is treated as non-match (conservative). That
    covers every call site inside this package; services requiring
    richer queries use the MongoDB backend.
    """
    for key, expected in filter.items():
        actual = doc.get(key)
        if (
            isinstance(expected, dict)
            and expected
            and any(k.startswith("$") for k in expected)
        ):
            for op, operand in expected.items():
                if op == "$in":
                    if actual not in operand:
                        return False
                elif op == "$exists":
                    if bool(operand) != (key in doc):
                        return False
                elif op == "$gte":
                    if actual is None or actual < operand:
                        return False
                elif op == "$lte":
                    if actual is None or actual > operand:
                        return False
                else:
                    # Unknown operator — conservative reject
                    return False
            continue
        if actual != expected:
            return False
    return True


def _sort_key(value: Any) -> tuple[int, Any]:
    """None-tolerant sort key.

    Python 3 refuses to compare ``None`` with other types; MongoDB
    sorts ``null`` before everything else. Emulated with a two-tuple:
    ``(is_none, value)`` so None bubbles to the end on ascending sort
    (matches MongoDB's default collation for the MCP-internal use).
    """
    return (0, value) if value is not None else (1, "")


def ensure_contract(backend: Any) -> "StorageBackend":
    """Runtime contract check for tests and loader code.

    ``isinstance(backend, StorageBackend)`` works because the protocol
    is ``runtime_checkable``, but it doesn't report missing attrs
    nicely. This helper raises ``TypeError`` with an actionable
    message.
    """
    required: Iterable[str] = ("mode", "ping", "insert", "query", "count", "delete")
    missing = [m for m in required if not hasattr(backend, m)]
    if missing:
        raise TypeError(
            f"{backend!r} does not satisfy StorageBackend; "
            f"missing: {', '.join(missing)}"
        )
    return backend  # type: ignore[return-value]


__all__ = [
    "StorageBackend",
    "InMemoryBackend",
    "ensure_contract",
]
