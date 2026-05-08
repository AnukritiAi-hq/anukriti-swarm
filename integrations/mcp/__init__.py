"""Anukriti Swarm — MCP-based infrastructure.

This package implements a Model-Context-Protocol-shaped infrastructure
layer for the swarm: a tool registry, an observability-wrapped client,
pluggable storage backends (in-memory by default, MongoDB when
configured), and per-concern services for execution memory, trace
persistence, context snapshotting, structured provenance, and evidence
caching.

The split follows the project's deterministic-first philosophy:

- ``integrations.mcp``           — generic, protocol-shaped infrastructure
                                    that treats every swarm operation as a
                                    named tool call with observability
- ``integrations.mongodb_mcp``   — legacy façade; now a thin wrapper that
                                    delegates to ``integrations.mcp``
                                    (kept so existing callers still work)

No network is required to use this package: the default backend is
in-memory, and the MongoDB backend is imported lazily only when both
``pymongo`` is installed **and** ``MONGODB_URI`` is set.

Public API is re-exported from submodules as they land in follow-up
commits. The empty ``__all__`` here will grow.
"""

from __future__ import annotations

__all__: list[str] = []
