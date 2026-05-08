"""Anukriti Swarm — MCP-based infrastructure.

Model-Context-Protocol-shaped infrastructure layer for the swarm:
tool registry, observability-wrapped client, pluggable storage backends
(in-memory by default, MongoDB when ``MONGODB_URI`` is set), and
per-concern services for execution memory, trace persistence, context
snapshotting, structured provenance, and evidence caching.

The split follows the project's deterministic-first philosophy:

- ``integrations.mcp``           — generic, protocol-shaped infrastructure
                                    that treats every swarm operation as a
                                    named tool call with observability
- ``integrations.mongodb_mcp``   — legacy façade; thin wrapper that
                                    delegates to ``integrations.mcp``
                                    (kept so existing callers still work)

No network is required: the default backend is in-memory, and the
MongoDB backend is imported lazily only when both ``pymongo`` is
installed **and** ``MONGODB_URI`` is set.

Quick start
-----------

    from integrations.mcp import (
        MCPClient,
        MCPExecutionMemory,
        MCPTraceStore,
        MCPContextManager,
        MCPProvenanceStore,
        MCPEvidenceCache,
    )

    client = MCPClient()  # auto-picks Mongo when MONGODB_URI is set
    memory   = MCPExecutionMemory(client)
    traces   = MCPTraceStore(client)
    contexts = MCPContextManager(client)
    prov     = MCPProvenanceStore(client)
    cache    = MCPEvidenceCache(client)

    # Every service registers its tools on the shared registry.
    client.list_tools()          # → sorted name + description
    client.snapshot()            # → observability rollup

Public API groups
-----------------

Core infrastructure:
    MCPClient, MCPToolRegistry, StorageBackend,
    InMemoryBackend, MongoDBBackend, load_default_backend

Data models:
    MCPOrigin, MCPToolCall, MCPToolResult, MCPObservability

Services (one class per concern, each attaches to a shared client):
    MCPExecutionMemory   — run-level persistent memory
    MCPTraceStore        — OrchestrationTrace persistence
    MCPContextManager    — SwarmExecutionContext snapshot/restore
    MCPProvenanceStore   — structured PROV-DM claim chains
    MCPEvidenceCache     — indexed biomedical evidence

Service-specific records:
    ProvenanceRecord

Collection name constants (useful for direct-backend queries):
    EXECUTIONS_COLLECTION, TRACES_COLLECTION, CONTEXTS_COLLECTION,
    PROVENANCE_COLLECTION, EVIDENCE_COLLECTION
"""

from __future__ import annotations

# --- Data models ---
from integrations.mcp.models import (
    MCPObservability,
    MCPOrigin,
    MCPToolCall,
    MCPToolResult,
)

# --- Backends ---
from integrations.mcp.backends import (
    InMemoryBackend,
    StorageBackend,
    ensure_contract,
    load_default_backend,
)

# --- Core infrastructure ---
from integrations.mcp.client import MCPClient
from integrations.mcp.registry import MCPToolRegistry, ToolHandler, ToolNotFoundError

# --- Services ---
from integrations.mcp.memory import EXECUTIONS_COLLECTION, MCPExecutionMemory
from integrations.mcp.trace_store import TRACES_COLLECTION, MCPTraceStore
from integrations.mcp.context_manager import CONTEXTS_COLLECTION, MCPContextManager
from integrations.mcp.provenance import (
    PROVENANCE_COLLECTION,
    MCPProvenanceStore,
    ProvenanceRecord,
)
from integrations.mcp.evidence import EVIDENCE_COLLECTION, MCPEvidenceCache


# MongoDB backend stays lazy — import only if pymongo is available.
# Users who want it directly can: ``from integrations.mcp.backends.mongo
# import MongoDBBackend``. We expose a guarded name here so the common
# import path stays the same.
try:
    from integrations.mcp.backends.mongo import MongoDBBackend  # noqa: F401

    _HAS_MONGO = True
except ImportError:  # pragma: no cover — pymongo is pinned in requirements
    _HAS_MONGO = False
    MongoDBBackend = None  # type: ignore[assignment,misc]


__all__ = [
    # Data models
    "MCPOrigin",
    "MCPToolCall",
    "MCPToolResult",
    "MCPObservability",
    # Backends
    "StorageBackend",
    "InMemoryBackend",
    "MongoDBBackend",
    "ensure_contract",
    "load_default_backend",
    # Core infrastructure
    "MCPClient",
    "MCPToolRegistry",
    "ToolHandler",
    "ToolNotFoundError",
    # Services
    "MCPExecutionMemory",
    "MCPTraceStore",
    "MCPContextManager",
    "MCPProvenanceStore",
    "MCPEvidenceCache",
    # Service records
    "ProvenanceRecord",
    # Collection constants
    "EXECUTIONS_COLLECTION",
    "TRACES_COLLECTION",
    "CONTEXTS_COLLECTION",
    "PROVENANCE_COLLECTION",
    "EVIDENCE_COLLECTION",
]
