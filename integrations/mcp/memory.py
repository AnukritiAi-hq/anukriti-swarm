"""``MCPExecutionMemory`` — persistent per-run agent memory.

This is the first of the per-concern MCP services. It owns the
``executions`` collection: one document per orchestration run, keyed
by ``correlation_id``, containing a summary of what happened.

Documents (JSON-safe, produced by ``store_run``):

    {
      "_id":            <backend-assigned>,
      "correlation_id": "abc123def456",
      "gene":           "CYP2C19",
      "drug":           "clopidogrel",
      "population":     "SAS",            # single-run
      "populations":    ["SAS","AFR"],    # comparative
      "drugs":          ["clopidogrel","omeprazole"],
      "genotype":       {"CYP2C19": "*2/*2"},
      "active_agents":  ["pharmacogene_cyp2c19", ...],
      "evidence_refs":  ["PMID:34032273", ...],
      "deterministic":  { ... snapshot of pgx / population / recs ... },
      "gemini_summary": { audience: str, ... },
      "verification_state": "passed",
      "phase":          "complete",
      "stored_at":      "2026-05-08T10:11:12+00:00"
    }

The service registers five MCP tools on the shared registry:

    memory.store        write a run summary
    memory.get          fetch by correlation_id
    memory.find         filter by gene/drug/population
    memory.recent       N most recent runs
    memory.history      run-level history for a given (gene, population)

Every public method on ``MCPExecutionMemory`` goes through the
registry, so the audit + observability hooks fire uniformly whether
the caller is an agent, the orchestrator, a demo script, or a replay
job. That keeps ``client.snapshot()`` honest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from integrations.mcp.client import MCPClient
from integrations.mcp.models import MCPOrigin, MCPToolResult


# Collection name — single source of truth, also referenced by the
# query APIs and the replay path.
EXECUTIONS_COLLECTION = "executions"


@dataclass
class MCPExecutionMemory:
    """Run-level persistent memory for the swarm.

    Attach one instance per ``MCPClient``; it auto-registers its tools
    on construction. Constructor is intentionally minimal so the
    service can be wired in a single line:

        mem = MCPExecutionMemory(client)
    """

    client: MCPClient
    collection: str = EXECUTIONS_COLLECTION

    def __post_init__(self) -> None:
        self._register()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _register(self) -> None:
        """Register memory tools on the shared registry.

        ``override=True`` so re-wiring a new service on the same client
        (for tests / replay) never crashes.
        """
        r = self.client.registry
        r.register(
            "memory.store",
            self._tool_store,
            description="Persist a run-level summary keyed by correlation_id.",
            origin=MCPOrigin.ORCHESTRATOR,
            override=True,
        )
        r.register(
            "memory.get",
            self._tool_get,
            description="Fetch a run summary by correlation_id.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "memory.find",
            self._tool_find,
            description="Find runs by any of gene/drug/population.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "memory.recent",
            self._tool_recent,
            description="Return the N most recent runs.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "memory.history",
            self._tool_history,
            description="All runs for a given gene+population pair, newest first.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )

    # ------------------------------------------------------------------
    # Python API (thin wrappers around registry.invoke)
    # ------------------------------------------------------------------

    def store_run(self, record: dict[str, Any]) -> MCPToolResult:
        """Persist a prepared run summary. See module docstring for shape."""
        return self.client.invoke(
            "memory.store",
            args={"record": record},
            correlation_id=str(record.get("correlation_id", "")),
            called_by="MCPExecutionMemory",
            origin=MCPOrigin.ORCHESTRATOR,
        )

    def get_run(self, correlation_id: str) -> MCPToolResult:
        return self.client.invoke(
            "memory.get",
            args={"correlation_id": correlation_id},
            correlation_id=correlation_id,
            called_by="MCPExecutionMemory",
        )

    def find_runs(
        self,
        *,
        gene: str = "",
        drug: str = "",
        population: str = "",
        limit: int = 20,
    ) -> MCPToolResult:
        return self.client.invoke(
            "memory.find",
            args={"gene": gene, "drug": drug, "population": population, "limit": limit},
            called_by="MCPExecutionMemory",
        )

    def recent(self, limit: int = 10) -> MCPToolResult:
        return self.client.invoke(
            "memory.recent",
            args={"limit": limit},
            called_by="MCPExecutionMemory",
        )

    def history_for(
        self, gene: str, population: str, *, limit: int = 20
    ) -> MCPToolResult:
        return self.client.invoke(
            "memory.history",
            args={"gene": gene, "population": population, "limit": limit},
            called_by="MCPExecutionMemory",
        )

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _tool_store(self, record: dict[str, Any]) -> dict[str, Any]:
        """Persist ``record``. Adds ``stored_at`` if missing."""
        if not isinstance(record, dict):
            raise TypeError("memory.store expects a dict record")
        if not record.get("correlation_id"):
            raise ValueError("memory.store requires correlation_id")

        doc = dict(record)
        doc.setdefault("stored_at", datetime.now(timezone.utc).isoformat())
        _id = self.client.backend.insert(self.collection, doc)
        return {"stored": True, "_id": _id, "correlation_id": doc["correlation_id"]}

    def _tool_get(self, correlation_id: str) -> dict[str, Any] | None:
        if not correlation_id:
            raise ValueError("memory.get requires correlation_id")
        rows = self.client.backend.query(
            self.collection,
            {"correlation_id": correlation_id},
            sort=[("stored_at", -1)],
            limit=1,
        )
        return rows[0] if rows else None

    def _tool_find(
        self,
        gene: str = "",
        drug: str = "",
        population: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        filter_: dict[str, Any] = {}
        if gene:
            filter_["gene"] = gene
        if drug:
            filter_["drug"] = drug
        if population:
            filter_["population"] = population
        return self.client.backend.query(
            self.collection, filter_ or None, sort=[("stored_at", -1)], limit=limit
        )

    def _tool_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.client.backend.query(
            self.collection, None, sort=[("stored_at", -1)], limit=int(limit)
        )

    def _tool_history(
        self, gene: str, population: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        if not gene and not population:
            raise ValueError("memory.history requires gene and/or population")
        filter_: dict[str, Any] = {}
        if gene:
            filter_["gene"] = gene
        if population:
            filter_["population"] = population
        return self.client.backend.query(
            self.collection, filter_, sort=[("stored_at", -1)], limit=int(limit)
        )


__all__ = ["MCPExecutionMemory", "EXECUTIONS_COLLECTION"]
