"""``MCPTraceStore`` — persistent step-level orchestration traces.

Persists the ``OrchestrationTrace`` objects produced by
``core.orchestrator.trace`` into the backend's ``traces`` collection,
with helpers to load them back for replay or audit.

One document per trace, shaped by ``OrchestrationTrace.to_dict()``
plus a ``stored_at`` timestamp and a flattened index on
``correlation_id`` for cheap lookup.

Tools registered:
  traces.store       write one full trace document
  traces.get         fetch a stored trace by correlation_id
  traces.recent      N most recent traces, newest first
  traces.step_count  cheap scalar helper for dashboards

Tools are narrow on purpose: the registry auditing already records
every ``client.invoke`` call, so granular replay lives at that layer
rather than here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from integrations.mcp.client import MCPClient
from integrations.mcp.models import MCPOrigin, MCPToolResult

# Late-bound import to avoid a hard dependency on the orchestrator
# package at module import time — ``OrchestrationTrace`` is only used
# for type-narrowing in ``store_trace``; plain dicts are accepted too.
try:  # pragma: no cover — always succeeds in this project
    from core.orchestrator.trace import OrchestrationTrace
except Exception:  # pragma: no cover — keeps the import dependency-light
    OrchestrationTrace = None  # type: ignore[assignment,misc]


TRACES_COLLECTION = "traces"


@dataclass
class MCPTraceStore:
    """Persistent store for ``OrchestrationTrace`` objects."""

    client: MCPClient
    collection: str = TRACES_COLLECTION

    def __post_init__(self) -> None:
        self._register()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _register(self) -> None:
        r = self.client.registry
        r.register(
            "traces.store",
            self._tool_store,
            description="Persist one OrchestrationTrace document.",
            origin=MCPOrigin.ORCHESTRATOR,
            override=True,
        )
        r.register(
            "traces.get",
            self._tool_get,
            description="Fetch a stored trace by correlation_id.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "traces.recent",
            self._tool_recent,
            description="Return the N most recent traces, newest first.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "traces.step_count",
            self._tool_step_count,
            description="Return the number of steps in a given trace.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )

    # ------------------------------------------------------------------
    # Python API
    # ------------------------------------------------------------------

    def store_trace(self, trace: Any) -> MCPToolResult:
        """Persist an ``OrchestrationTrace`` (or its ``to_dict()`` form)."""
        payload = self._coerce_trace(trace)
        return self.client.invoke(
            "traces.store",
            args={"trace": payload},
            correlation_id=str(payload.get("correlation_id", "")),
            called_by="MCPTraceStore",
            origin=MCPOrigin.ORCHESTRATOR,
        )

    def get_trace(self, correlation_id: str) -> MCPToolResult:
        return self.client.invoke(
            "traces.get",
            args={"correlation_id": correlation_id},
            correlation_id=correlation_id,
            called_by="MCPTraceStore",
        )

    def recent(self, limit: int = 10) -> MCPToolResult:
        return self.client.invoke(
            "traces.recent",
            args={"limit": limit},
            called_by="MCPTraceStore",
        )

    def step_count(self, correlation_id: str) -> MCPToolResult:
        return self.client.invoke(
            "traces.step_count",
            args={"correlation_id": correlation_id},
            correlation_id=correlation_id,
            called_by="MCPTraceStore",
        )

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _tool_store(self, trace: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(trace, dict):
            raise TypeError("traces.store expects a dict trace payload")
        cid = trace.get("correlation_id") or ""
        if not cid:
            raise ValueError("traces.store requires correlation_id on the trace")
        doc = dict(trace)
        doc.setdefault("stored_at", datetime.now(timezone.utc).isoformat())
        doc["step_count"] = len(doc.get("steps") or [])
        doc["activation_count"] = len(doc.get("activations") or [])
        _id = self.client.backend.insert(self.collection, doc)
        return {"stored": True, "_id": _id, "correlation_id": cid}

    def _tool_get(self, correlation_id: str) -> dict[str, Any] | None:
        if not correlation_id:
            raise ValueError("traces.get requires correlation_id")
        rows = self.client.backend.query(
            self.collection,
            {"correlation_id": correlation_id},
            sort=[("stored_at", -1)],
            limit=1,
        )
        return rows[0] if rows else None

    def _tool_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.client.backend.query(
            self.collection, None, sort=[("stored_at", -1)], limit=int(limit)
        )

    def _tool_step_count(self, correlation_id: str) -> int:
        doc = self._tool_get(correlation_id)
        if not doc:
            return 0
        return int(doc.get("step_count") or len(doc.get("steps") or []))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_trace(trace: Any) -> dict[str, Any]:
        """Accept an OrchestrationTrace, a dict, or anything with to_dict()."""
        if isinstance(trace, dict):
            return trace
        to_dict = getattr(trace, "to_dict", None)
        if callable(to_dict):
            result = to_dict()
            if isinstance(result, dict):
                return result
        raise TypeError(
            f"cannot coerce {type(trace).__name__!r} into a trace dict; "
            "pass an OrchestrationTrace or its to_dict() output"
        )


__all__ = ["MCPTraceStore", "TRACES_COLLECTION"]
