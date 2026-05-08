"""MongoDB-backed ``StorageBackend`` implementation.

Lazily instantiates a ``pymongo.MongoClient`` and maps every collection
name straight through to ``client[db_name][collection]``. The filter,
sort, and limit contracts on ``StorageBackend`` are deliberately
identical to MongoDB's own, so forwarding is trivial.

Connection lifecycle
--------------------
- ``MongoDBBackend(uri, db_name)`` builds a client with a short server
  selection timeout (5s). That makes connection failures surface fast
  rather than hanging the process.
- ``ping()`` runs a ``admin.command('ping')`` and caches the result
  for a short interval. It is the single check the loader uses to
  decide whether to return this backend vs fall back to in-memory.
- Callers should treat this object as long-lived; pymongo maintains
  its own connection pool internally.

Error policy
------------
pymongo exceptions propagate. The loader
(``integrations.mcp.backends.load_default_backend``) catches them and
falls back to in-memory — so top-level demos still run even when Atlas
is unreachable. Services that *require* persistence should instantiate
``MongoDBBackend`` directly and let exceptions bubble.
"""

from __future__ import annotations

import os
import time
from typing import Any

try:
    from pymongo import ASCENDING, DESCENDING, MongoClient
except ImportError as exc:  # pragma: no cover — surfaced by the loader
    raise ImportError(
        "pymongo is required for MongoDBBackend. "
        "Install with: pip install 'pymongo[srv]'"
    ) from exc


# Cache the ping result for this many seconds to avoid spamming Atlas
# during tight loops (the loader, tests, the MCP client dashboard).
_PING_CACHE_SECONDS = 5.0


class MongoDBBackend:
    """``StorageBackend`` implementation wrapping a ``pymongo.MongoClient``.

    Parameters
    ----------
    uri:
        Full MongoDB connection string. Defaults to ``MONGODB_URI`` env
        var if omitted.
    db_name:
        Database name. Defaults to ``MONGODB_DB`` env var, then
        ``"anukriti_swarm"``.
    server_selection_timeout_ms:
        How long pymongo waits to find a usable server before raising.
        Short by design — we want fast failure so the loader can
        fall back.
    """

    def __init__(
        self,
        uri: str | None = None,
        db_name: str | None = None,
        *,
        server_selection_timeout_ms: int = 5000,
    ) -> None:
        self.uri = uri or os.environ.get("MONGODB_URI", "")
        if not self.uri:
            raise ValueError(
                "MongoDBBackend requires a uri or MONGODB_URI env var"
            )
        self.db_name = db_name or os.environ.get("MONGODB_DB", "anukriti_swarm")
        self._client: MongoClient = MongoClient(
            self.uri,
            serverSelectionTimeoutMS=server_selection_timeout_ms,
            appname="anukriti-swarm-mcp",
        )
        self._db = self._client[self.db_name]
        self._ping_ok_until: float = 0.0
        self._ping_ok: bool = False

    # ----- informational --------------------------------------------

    @property
    def mode(self) -> str:
        return "mongodb_atlas"

    def ping(self) -> bool:
        """Cheap health check with a short-lived cache."""
        now = time.time()
        if now < self._ping_ok_until and self._ping_ok:
            return True
        try:
            self._client.admin.command("ping")
            self._ping_ok = True
        except Exception:
            self._ping_ok = False
        self._ping_ok_until = now + _PING_CACHE_SECONDS
        return self._ping_ok

    # ----- CRUD -----------------------------------------------------

    def insert(self, collection: str, doc: dict[str, Any]) -> str:
        """Insert ``doc`` and return the string form of its ``_id``."""
        coll = self._db[collection]
        # Don't mutate the caller's dict.
        payload = dict(doc)
        result = coll.insert_one(payload)
        return str(payload.get("_id", result.inserted_id))

    def query(
        self,
        collection: str,
        filter: dict[str, Any] | None = None,
        *,
        sort: list[tuple[str, int]] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Forward to pymongo's find(), casting _id to str on the way out."""
        coll = self._db[collection]
        cursor = coll.find(filter or {})
        if sort:
            cursor = cursor.sort(
                [(f, ASCENDING if d >= 0 else DESCENDING) for f, d in sort]
            )
        if limit is not None:
            cursor = cursor.limit(int(limit))

        rows: list[dict[str, Any]] = []
        for doc in cursor:
            # MCP services treat _id as a string. pymongo returns an
            # ObjectId. Coerce so downstream code is backend-agnostic.
            if "_id" in doc and not isinstance(doc["_id"], str):
                doc["_id"] = str(doc["_id"])
            rows.append(doc)
        return rows

    def count(
        self, collection: str, filter: dict[str, Any] | None = None
    ) -> int:
        return int(self._db[collection].count_documents(filter or {}))

    def delete(self, collection: str, filter: dict[str, Any]) -> int:
        if not filter:
            # Refuse to drop entire collections via the abstract backend
            # interface. Do it via ``self._db.drop_collection`` if you
            # really must.
            raise ValueError("delete() requires a non-empty filter")
        return int(self._db[collection].delete_many(filter).deleted_count)

    # ----- debugging helper -----------------------------------------

    def close(self) -> None:
        """Release the underlying pymongo client. Idempotent."""
        try:
            self._client.close()
        except Exception:
            pass


__all__ = ["MongoDBBackend"]
