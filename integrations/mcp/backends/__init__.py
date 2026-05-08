"""Storage backends for the MCP infrastructure.

Submodules:
- ``base``  — ``StorageBackend`` protocol and in-memory default
- ``mongo`` — MongoDB-backed implementation (added in a follow-up commit)

The MongoDB backend is imported on demand via ``load_default_backend``
so this package stays importable when pymongo is not installed.
"""

from __future__ import annotations

import os

from integrations.mcp.backends.base import (
    InMemoryBackend,
    StorageBackend,
    ensure_contract,
)


def load_default_backend() -> StorageBackend:
    """Pick the best available backend given the current environment.

    Order:
      1. ``MONGODB_URI`` is set AND pymongo is installed → ``MongoDBBackend``
         (falls through on import or connectivity errors)
      2. otherwise → ``InMemoryBackend``
    """
    uri = os.environ.get("MONGODB_URI")
    if uri:
        try:
            from integrations.mcp.backends.mongo import MongoDBBackend

            backend = MongoDBBackend(uri=uri)
            if backend.ping():
                return backend
        except ImportError:
            # pymongo not installed — fall through to in-memory.
            pass
        except Exception:
            # Network / auth failure — fall through rather than crash.
            # Callers that *require* Mongo should instantiate
            # MongoDBBackend directly and handle exceptions themselves.
            pass
    return InMemoryBackend()


__all__ = [
    "StorageBackend",
    "InMemoryBackend",
    "ensure_contract",
    "load_default_backend",
]
