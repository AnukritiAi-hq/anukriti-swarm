"""``MCPContextManager`` — snapshot + restore ``SwarmExecutionContext``.

Separate from ``MCPExecutionMemory`` on purpose:

- ``MCPExecutionMemory``      owns **run summaries** — compact views
                               produced by the orchestrator after a run
                               completes (gene, drug, verdict, citations,
                               ...). Shaped for lookup + dashboards.
- ``MCPContextManager``       owns **full context snapshots** — the
                               raw ``SwarmExecutionContext`` at some
                               point in the lifecycle. Shaped for
                               replay + resume-after-escalation.

Multiple snapshots per ``correlation_id`` are allowed; ``load``
returns the newest, ``history`` returns all of them in reverse
chronological order. That makes it natural to snapshot at several
lifecycle points (PLANNING, ROUTING, ESCALATED, COMPLETE) without
losing intermediate state.

Tools registered:
  context.snapshot    persist one context snapshot
  context.load        dict form of newest snapshot
  context.restore     rehydrated SwarmExecutionContext
  context.recent      N most recent snapshots across all runs
  context.history     all snapshots for a single correlation_id
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from integrations.mcp.client import MCPClient
from integrations.mcp.models import MCPOrigin, MCPToolResult

# Late-bound import so the MCP package stays importable if the
# orchestrator package is ever refactored independently.
try:  # pragma: no cover
    from core.orchestrator.context import SwarmExecutionContext
except Exception:  # pragma: no cover
    SwarmExecutionContext = None  # type: ignore[assignment,misc]


CONTEXTS_COLLECTION = "contexts"

# Fields persisted through ``exclude`` to ``model_dump`` — we don't
# want to duplicate the trace here (``MCPTraceStore`` owns it) and
# we skip the ``verification_report`` blob because it can be huge.
_SNAPSHOT_EXCLUDE = {"orchestration_trace", "verification_report"}


@dataclass
class MCPContextManager:
    """Persistent snapshot/restore for ``SwarmExecutionContext``."""

    client: MCPClient
    collection: str = CONTEXTS_COLLECTION

    def __post_init__(self) -> None:
        self._register()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _register(self) -> None:
        r = self.client.registry
        r.register(
            "context.snapshot",
            self._tool_snapshot,
            description="Persist one SwarmExecutionContext snapshot.",
            origin=MCPOrigin.ORCHESTRATOR,
            override=True,
        )
        r.register(
            "context.load",
            self._tool_load,
            description="Fetch the newest snapshot as a dict.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "context.restore",
            self._tool_restore,
            description="Rehydrate newest snapshot into a SwarmExecutionContext.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "context.recent",
            self._tool_recent,
            description="N most recent snapshots across all runs.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "context.history",
            self._tool_history,
            description="All snapshots for a correlation_id, newest first.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )

    # ------------------------------------------------------------------
    # Python API
    # ------------------------------------------------------------------

    def snapshot(self, ctx: Any) -> MCPToolResult:
        """Persist ``ctx`` (SwarmExecutionContext or dict form)."""
        payload = self._coerce_context(ctx)
        return self.client.invoke(
            "context.snapshot",
            args={"context": payload},
            correlation_id=str(payload.get("correlation_id", "")),
            called_by="MCPContextManager",
            origin=MCPOrigin.ORCHESTRATOR,
        )

    def load(self, correlation_id: str) -> MCPToolResult:
        return self.client.invoke(
            "context.load",
            args={"correlation_id": correlation_id},
            correlation_id=correlation_id,
            called_by="MCPContextManager",
        )

    def restore(self, correlation_id: str) -> MCPToolResult:
        return self.client.invoke(
            "context.restore",
            args={"correlation_id": correlation_id},
            correlation_id=correlation_id,
            called_by="MCPContextManager",
        )

    def recent(self, limit: int = 10) -> MCPToolResult:
        return self.client.invoke(
            "context.recent",
            args={"limit": limit},
            called_by="MCPContextManager",
        )

    def history(self, correlation_id: str, *, limit: int = 20) -> MCPToolResult:
        return self.client.invoke(
            "context.history",
            args={"correlation_id": correlation_id, "limit": limit},
            correlation_id=correlation_id,
            called_by="MCPContextManager",
        )

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _tool_snapshot(self, context: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(context, dict):
            raise TypeError("context.snapshot expects a dict payload")
        cid = context.get("correlation_id") or ""
        if not cid:
            raise ValueError("context.snapshot requires correlation_id")
        doc = dict(context)
        doc.setdefault("snapshotted_at", datetime.now(timezone.utc).isoformat())
        _id = self.client.backend.insert(self.collection, doc)
        return {"stored": True, "_id": _id, "correlation_id": cid}

    def _tool_load(self, correlation_id: str) -> dict[str, Any] | None:
        if not correlation_id:
            raise ValueError("context.load requires correlation_id")
        rows = self.client.backend.query(
            self.collection,
            {"correlation_id": correlation_id},
            sort=[("snapshotted_at", -1)],
            limit=1,
        )
        return rows[0] if rows else None

    def _tool_restore(self, correlation_id: str) -> Any:
        """Rehydrate into a ``SwarmExecutionContext``.

        Returns the real Pydantic model when ``SwarmExecutionContext``
        is importable (default path), otherwise the raw dict. Returns
        ``None`` if no snapshot exists — callers should treat that as
        'nothing to replay' rather than a hard error.
        """
        doc = self._tool_load(correlation_id)
        if doc is None:
            return None
        if SwarmExecutionContext is None:
            return doc
        return _rehydrate(doc)

    def _tool_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.client.backend.query(
            self.collection, None, sort=[("snapshotted_at", -1)], limit=int(limit)
        )

    def _tool_history(
        self, correlation_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        if not correlation_id:
            raise ValueError("context.history requires correlation_id")
        return self.client.backend.query(
            self.collection,
            {"correlation_id": correlation_id},
            sort=[("snapshotted_at", -1)],
            limit=int(limit),
        )

    # ------------------------------------------------------------------
    # Coercion / rehydration
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_context(ctx: Any) -> dict[str, Any]:
        """Accept a ``SwarmExecutionContext``, dict, or model_dump output."""
        if isinstance(ctx, dict):
            return ctx

        # Pydantic v2 path
        model_dump = getattr(ctx, "model_dump", None)
        if callable(model_dump):
            try:
                return model_dump(exclude=_SNAPSHOT_EXCLUDE, mode="json")
            except TypeError:
                # Older Pydantic / incompatible signature — fall through.
                return model_dump(exclude=_SNAPSHOT_EXCLUDE)

        # Plain dataclass fallback
        to_dict = getattr(ctx, "to_dict", None)
        if callable(to_dict):
            result = to_dict()
            if isinstance(result, dict):
                return {k: v for k, v in result.items() if k not in _SNAPSHOT_EXCLUDE}

        raise TypeError(
            f"cannot coerce {type(ctx).__name__!r} into a context dict; "
            "pass a SwarmExecutionContext or its model_dump() output"
        )


# ---------------------------------------------------------------------------
# Rehydration
# ---------------------------------------------------------------------------


def _rehydrate(doc: dict[str, Any]) -> Any:
    """Best-effort ``dict -> SwarmExecutionContext`` using Pydantic validation.

    Pydantic handles enum coercion (``OrchestrationPhase``,
    ``VerificationState``), datetime parsing, and default-fill for any
    fields we excluded on the write path. Unknown fields (e.g. the
    stored ``snapshotted_at``, ``_id``) are skipped with the strict
    validator; we filter them out explicitly for clarity.
    """
    # Drop backend-internal / snapshot-bookkeeping fields.
    scrub_keys = {"_id", "snapshotted_at"}
    cleaned = {k: v for k, v in doc.items() if k not in scrub_keys}
    # Re-inject the excluded-on-write fields with sensible defaults so
    # Pydantic's required-field validation stays happy.
    cleaned.setdefault("orchestration_trace", None)
    cleaned.setdefault("verification_report", {})
    return SwarmExecutionContext.model_validate(cleaned)  # type: ignore[union-attr]


__all__ = ["MCPContextManager", "CONTEXTS_COLLECTION"]
