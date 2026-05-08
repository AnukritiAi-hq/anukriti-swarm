"""MongoDB MCP facade — thin shim over ``integrations.mcp``.

Historical context
------------------
This module was the *first* MCP integration in the project. It shipped
four concern-specific helpers (``memory_*``, ``traces_*``,
``provenance_*``, ``evidence_*``) on a single ``MongoDBMCP`` class
with its own ad-hoc in-memory fallback and its own ``MongoClient``.

Since then the swarm has grown a proper MCP infrastructure at
``integrations.mcp`` with:

  - a pluggable ``StorageBackend`` (in-memory / MongoDB / test fakes)
  - a shared ``MCPToolRegistry`` + observability
  - per-concern services (``MCPExecutionMemory``, ``MCPTraceStore``,
    ``MCPContextManager``, ``MCPProvenanceStore``, ``MCPEvidenceCache``)

This module now exists solely to keep the legacy call sites — most
notably ``integrations.google_adk.orchestrator`` and
``demos/adk_demo.py`` — working without rewriting them. Every method
delegates to the new MCP layer; no independent state lives here.

Why keep it at all?
-------------------
Two reasons:
  1. The legacy demo uses the domain-flavored verb-noun API
     (``traces_log(correlation_id, stage, agent_id, result)``) which
     maps cleanly onto the new services but is more ergonomic for
     that specific call site than the raw ``client.invoke(...)``
     idiom.
  2. It lets callers upgrade incrementally. New code should import
     directly from ``integrations.mcp``; old code keeps working.

The ``mode`` property + ``get_stats()`` method preserve the exact
shape the hackathon demo prints to stdout so the UX is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from integrations.mcp import (
    EVIDENCE_COLLECTION,
    EXECUTIONS_COLLECTION,
    MCPClient,
    MCPEvidenceCache,
    MCPExecutionMemory,
    MCPProvenanceStore,
    MCPTraceStore,
    PROVENANCE_COLLECTION,
    TRACES_COLLECTION,
)


# ---------------------------------------------------------------------------
# Legacy result shape (preserved for backward compatibility)
# ---------------------------------------------------------------------------


@dataclass
class MCPToolResult:
    """Legacy result shape.

    Kept for callers that inspect ``.success`` / ``.data`` / ``.tool``.
    New code should use ``integrations.mcp.models.MCPToolResult`` which
    is richer (``latency_ms``, ``tool_call_id``, ``.ok``/``.fail``
    constructors).
    """

    tool: str
    success: bool
    data: Any
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------


class MongoDBMCP:
    """Facade preserving the original ``MongoDBMCP`` API surface.

    Internally composes an ``MCPClient`` + the four relevant services
    (memory, traces, provenance, evidence). Backend selection is
    delegated to ``MCPClient``'s default loader:
    MongoDB when ``MONGODB_URI`` is set and reachable, else in-memory.

    Legacy callers get:

        mcp = MongoDBMCP()
        mcp.memory_store(agent_id, correlation_id, data)
        mcp.traces_log(correlation_id, stage, agent_id, result)
        mcp.provenance_record(correlation_id, claim, source, confidence)
        mcp.evidence_index(gene, content, source_id, metadata)
        mcp.evidence_search(gene, limit=5)
        mcp.get_stats()
    """

    def __init__(self, *, client: MCPClient | None = None) -> None:
        self._client = client or MCPClient()
        # Wire the four services we need; ``context`` is not part of
        # the legacy API so we don't attach it here.
        self._memory = MCPExecutionMemory(client=self._client)
        self._traces = MCPTraceStore(client=self._client)
        self._provenance = MCPProvenanceStore(client=self._client)
        self._evidence = MCPEvidenceCache(client=self._client)

    # ------------------------------------------------------------------
    # Legacy properties
    # ------------------------------------------------------------------

    @property
    def connected(self) -> bool:
        """True when the underlying backend is live (Mongo or in-memory)."""
        return self._client.ping()

    @property
    def mode(self) -> str:
        """Backend mode string: ``'mongodb_atlas'`` or ``'in_memory'``."""
        return self._client.mode

    @property
    def client(self) -> MCPClient:
        """Expose the composed MCPClient for callers that want the new API."""
        return self._client

    # ------------------------------------------------------------------
    # Memory Tools
    # ------------------------------------------------------------------

    def memory_store(
        self, agent_id: str, correlation_id: str, data: dict[str, Any]
    ) -> MCPToolResult:
        """Store per-agent state. Maps onto ``memory.store`` with a
        minimal record wrapper so the legacy (agent_id, data) payload
        still round-trips.
        """
        record = {
            "correlation_id": correlation_id,
            "agent_id": agent_id,
            "data": dict(data or {}),
            "legacy": True,  # tag so queries can distinguish from orchestrator runs
        }
        r = self._memory.store_run(record)
        return MCPToolResult(
            tool="memory.store", success=r.success, data=r.data, latency_ms=r.latency_ms
        )

    def memory_retrieve(self, agent_id: str, limit: int = 5) -> MCPToolResult:
        """Retrieve last N memory entries for an agent.

        The new ``MCPExecutionMemory`` indexes by (gene, drug, population)
        not by agent_id, so we read the raw collection and filter. This
        works uniformly against in-memory and Mongo backends.
        """
        rows = self._client.backend.query(
            EXECUTIONS_COLLECTION,
            {"agent_id": agent_id},
            sort=[("stored_at", -1)],
            limit=int(limit),
        )
        return MCPToolResult(tool="memory.retrieve", success=True, data=rows)

    # ------------------------------------------------------------------
    # Trace Tools
    # ------------------------------------------------------------------

    def traces_log(
        self,
        correlation_id: str,
        stage: str,
        agent_id: str,
        result: dict[str, Any],
    ) -> MCPToolResult:
        """Append one stage entry to the trace collection.

        This is the legacy "append one row per stage" pattern. The new
        ``MCPTraceStore`` stores a whole ``OrchestrationTrace`` as a
        single document, so rather than force an artificial shape we
        write directly to the ``traces`` collection here with the
        legacy row shape. ``MCPRetrieval.lookup`` still sees these
        rows because it queries the collection, not just single-doc
        traces.
        """
        row = {
            "correlation_id": correlation_id,
            "stage": stage,
            "agent_id": agent_id,
            "result": dict(result or {}),
            "legacy": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _id = self._client.backend.insert(TRACES_COLLECTION, row)
        return MCPToolResult(
            tool="traces.log", success=True, data={"logged": True, "_id": _id}
        )

    def traces_query(self, correlation_id: str) -> MCPToolResult:
        """Return all trace rows for a correlation_id (legacy + new shape)."""
        rows = self._client.backend.query(
            TRACES_COLLECTION,
            {"correlation_id": correlation_id},
            sort=[("timestamp", 1)],
        )
        return MCPToolResult(tool="traces.query", success=True, data=rows)

    # ------------------------------------------------------------------
    # Provenance Tools
    # ------------------------------------------------------------------

    def provenance_record(
        self,
        correlation_id: str,
        claim: str,
        source: str,
        confidence: float,
    ) -> MCPToolResult:
        """Legacy flat provenance row → structured ``ProvenanceRecord``.

        The legacy shape carried four fields (correlation, claim, source,
        confidence). We populate the new PROV-DM fields with sensible
        defaults so the record is still queryable via the new APIs
        (``provenance.for_run`` etc.).
        """
        r = self._provenance.record_claim(
            claim=claim,
            generating_agent="legacy",
            rule_id="legacy.flat",
            correlation_id=correlation_id,
            evidence_sources=[source] if source else [],
            verification_verdict="pending",
            confidence=float(confidence or 1.0),
            origin="deterministic",
            metadata={"legacy": True},
        )
        return MCPToolResult(
            tool="provenance.record",
            success=r.success,
            data=r.data,
            latency_ms=r.latency_ms,
        )

    # ------------------------------------------------------------------
    # Evidence Tools
    # ------------------------------------------------------------------

    def evidence_index(
        self,
        gene: str,
        content: str,
        source_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        r = self._evidence.index(
            source_id=source_id, content=content, gene=gene, metadata=metadata or {}
        )
        return MCPToolResult(
            tool="evidence.index",
            success=r.success,
            data=r.data,
            latency_ms=r.latency_ms,
        )

    def evidence_search(self, gene: str, limit: int = 5) -> MCPToolResult:
        r = self._evidence.by_gene(gene, limit=limit)
        return MCPToolResult(
            tool="evidence.search",
            success=r.success,
            data=list(r.data or []),
            latency_ms=r.latency_ms,
        )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, int]:
        """Row counts per collection — shape preserved for the legacy demo."""
        b = self._client.backend
        return {
            "memory": b.count(EXECUTIONS_COLLECTION),
            "traces": b.count(TRACES_COLLECTION),
            "provenance": b.count(PROVENANCE_COLLECTION),
            "evidence": b.count(EVIDENCE_COLLECTION),
        }


__all__ = ["MongoDBMCP", "MCPToolResult"]
