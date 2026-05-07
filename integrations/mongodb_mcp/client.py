"""MongoDB MCP integration for swarm memory, traces, and provenance.

Provides MCP-compatible tool interface for:
- Agent memory persistence
- Execution trace storage
- Provenance chain logging
- Evidence indexing
- Retrieval context caching

Works in mock mode without MongoDB connection (for demos).
Connects to real MongoDB Atlas when MONGODB_URI is set.
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MCPToolResult:
    """Result from an MCP tool invocation."""

    tool: str
    success: bool
    data: Any
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MongoDBMCP:
    """MongoDB MCP client for swarm memory infrastructure.

    MCP tools exposed:
    - memory.store: persist agent state/results
    - memory.retrieve: recall previous executions
    - traces.log: append execution trace entry
    - traces.query: retrieve traces by correlation_id
    - provenance.record: log provenance chain entry
    - evidence.index: store evidence for retrieval
    - evidence.search: search indexed evidence

    Falls back to in-memory storage when MongoDB is unavailable.
    """

    def __init__(self) -> None:
        self.uri = os.environ.get("MONGODB_URI")
        self._db: Any = None
        self._memory: dict[str, list[dict]] = {
            "memory": [], "traces": [], "provenance": [], "evidence": [],
        }

        if self.uri:
            try:
                from pymongo import MongoClient
                client = MongoClient(self.uri)
                self._db = client.anukriti_swarm
            except Exception:
                pass

    @property
    def connected(self) -> bool:
        return self._db is not None

    @property
    def mode(self) -> str:
        return "mongodb_atlas" if self.connected else "in_memory"

    # --- Memory Tools ---

    def memory_store(self, agent_id: str, correlation_id: str, data: dict[str, Any]) -> MCPToolResult:
        """Store agent memory/state."""
        doc = {"agent_id": agent_id, "correlation_id": correlation_id, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()}
        if self.connected:
            self._db.memory.insert_one(doc)
        else:
            self._memory["memory"].append(doc)
        return MCPToolResult(tool="memory.store", success=True, data={"stored": True})

    def memory_retrieve(self, agent_id: str, limit: int = 5) -> MCPToolResult:
        """Retrieve agent memory."""
        if self.connected:
            docs = list(self._db.memory.find({"agent_id": agent_id}).sort("timestamp", -1).limit(limit))
        else:
            docs = [d for d in self._memory["memory"] if d["agent_id"] == agent_id][-limit:]
        return MCPToolResult(tool="memory.retrieve", success=True, data=docs)

    # --- Trace Tools ---

    def traces_log(self, correlation_id: str, stage: str, agent_id: str, result: dict[str, Any]) -> MCPToolResult:
        """Log an execution trace entry."""
        doc = {"correlation_id": correlation_id, "stage": stage, "agent_id": agent_id, "result": result, "timestamp": datetime.now(timezone.utc).isoformat()}
        if self.connected:
            self._db.traces.insert_one(doc)
        else:
            self._memory["traces"].append(doc)
        return MCPToolResult(tool="traces.log", success=True, data={"logged": True})

    def traces_query(self, correlation_id: str) -> MCPToolResult:
        """Query traces by correlation_id."""
        if self.connected:
            docs = list(self._db.traces.find({"correlation_id": correlation_id}).sort("timestamp", 1))
        else:
            docs = [d for d in self._memory["traces"] if d["correlation_id"] == correlation_id]
        return MCPToolResult(tool="traces.query", success=True, data=docs)

    # --- Provenance Tools ---

    def provenance_record(self, correlation_id: str, claim: str, source: str, confidence: float) -> MCPToolResult:
        """Record a provenance chain entry."""
        doc = {"correlation_id": correlation_id, "claim": claim, "source": source, "confidence": confidence, "timestamp": datetime.now(timezone.utc).isoformat()}
        if self.connected:
            self._db.provenance.insert_one(doc)
        else:
            self._memory["provenance"].append(doc)
        return MCPToolResult(tool="provenance.record", success=True, data={"recorded": True})

    # --- Evidence Tools ---

    def evidence_index(self, gene: str, content: str, source_id: str, metadata: dict[str, Any] | None = None) -> MCPToolResult:
        """Index evidence for retrieval."""
        doc = {"gene": gene, "content": content, "source_id": source_id, "metadata": metadata or {}, "timestamp": datetime.now(timezone.utc).isoformat()}
        if self.connected:
            self._db.evidence.insert_one(doc)
        else:
            self._memory["evidence"].append(doc)
        return MCPToolResult(tool="evidence.index", success=True, data={"indexed": True})

    def evidence_search(self, gene: str, limit: int = 5) -> MCPToolResult:
        """Search indexed evidence by gene."""
        if self.connected:
            docs = list(self._db.evidence.find({"gene": gene}).limit(limit))
        else:
            docs = [d for d in self._memory["evidence"] if d["gene"] == gene][:limit]
        return MCPToolResult(tool="evidence.search", success=True, data=docs)

    # --- Summary ---

    def get_stats(self) -> dict[str, int]:
        """Get storage statistics."""
        if self.connected:
            return {k: self._db[k].count_documents({}) for k in ["memory", "traces", "provenance", "evidence"]}
        return {k: len(v) for k, v in self._memory.items()}
