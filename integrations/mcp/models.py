"""Shared MCP data models.

These are the lightweight dataclasses every piece of the MCP
infrastructure speaks in. They are:

- cheap to create (dataclasses, not Pydantic) because they sit on the
  hot path of every tool call
- JSON-serializable via explicit ``to_dict`` so they can drop straight
  into the MongoDB backend or the ``visualization.export`` pipeline
- annotated with an ``origin`` tag that mirrors
  ``core.orchestrator.trace.Origin`` — the MCP layer therefore remains
  observable under the same deterministic/generative boundary lens
  used elsewhere in the codebase.

Exports
-------
``MCPOrigin``      — who invoked a tool (agent / orchestrator / user / system)
``MCPToolCall``    — immutable record of a tool invocation
``MCPToolResult``  — outcome of a tool invocation (success or failure)
``MCPObservability`` — rolling counters + per-tool aggregates
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MCPOrigin(str, Enum):
    """Who triggered a tool call."""

    AGENT = "agent"                # a specialist agent requested the tool
    ORCHESTRATOR = "orchestrator"  # the GeminiOrchestrator or ADKOrchestrator
    USER = "user"                  # direct API / demo caller
    SYSTEM = "system"              # background job, replay, housekeeping


# ---------------------------------------------------------------------------
# Tool call + result
# ---------------------------------------------------------------------------


@dataclass
class MCPToolCall:
    """Immutable record of one tool invocation.

    The registry creates one of these for every dispatch. Paired with
    the ``MCPToolResult`` on the same ``id`` it becomes an auditable
    before/after record for a single MCP operation.
    """

    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    origin: MCPOrigin = MCPOrigin.SYSTEM
    called_by: str = ""  # e.g. agent_id or "orchestrator"
    correlation_id: str = ""  # links a tool call to a workflow run
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tool": self.tool,
            "args": _json_safe(self.args),
            "origin": self.origin.value,
            "called_by": self.called_by,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MCPToolResult:
    """Outcome of a tool invocation.

    Use the ``ok`` / ``fail`` classmethods rather than the constructor
    directly so the two success / failure paths stay symmetric. The
    raw constructor is kept for deserialization and test fakes.
    """

    tool: str
    success: bool
    data: Any = None
    error: str = ""
    latency_ms: float = 0.0
    tool_call_id: str = ""  # links to MCPToolCall.id
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ------------------- constructors -------------------

    @classmethod
    def ok(
        cls,
        tool: str,
        data: Any = None,
        *,
        latency_ms: float = 0.0,
        tool_call_id: str = "",
    ) -> "MCPToolResult":
        return cls(
            tool=tool,
            success=True,
            data=data,
            latency_ms=latency_ms,
            tool_call_id=tool_call_id,
        )

    @classmethod
    def fail(
        cls,
        tool: str,
        error: str,
        *,
        latency_ms: float = 0.0,
        tool_call_id: str = "",
    ) -> "MCPToolResult":
        return cls(
            tool=tool,
            success=False,
            error=error,
            latency_ms=latency_ms,
            tool_call_id=tool_call_id,
        )

    # ------------------- serialization ------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "success": self.success,
            "data": _json_safe(self.data),
            "error": self.error,
            "latency_ms": self.latency_ms,
            "tool_call_id": self.tool_call_id,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------


@dataclass
class _PerToolCounters:
    """Private bucket of counters for a single tool name."""

    calls: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.calls if self.calls else 0.0


@dataclass
class MCPObservability:
    """In-process counters for the MCP layer.

    Records every ``MCPToolResult`` via ``record(...)`` and produces a
    ``snapshot()`` dict suitable for periodic logging, dashboard
    rendering, or JSON export.

    Not thread-safe (yet) — the swarm currently runs on a single event
    loop per orchestrator. Add a lock here if that changes.
    """

    calls: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0
    by_tool: dict[str, _PerToolCounters] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def record(self, result: MCPToolResult) -> None:
        """Fold a tool result into the rolling counters."""
        self.calls += 1
        self.total_latency_ms += result.latency_ms
        if not result.success:
            self.failures += 1

        bucket = self.by_tool.setdefault(result.tool, _PerToolCounters())
        bucket.calls += 1
        bucket.total_latency_ms += result.latency_ms
        if not result.success:
            bucket.failures += 1

    @property
    def success_rate(self) -> float:
        if not self.calls:
            return 1.0
        return 1.0 - (self.failures / self.calls)

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.calls if self.calls else 0.0

    def snapshot(self) -> dict[str, Any]:
        """JSON-safe rollup for dashboards / logs."""
        return {
            "calls": self.calls,
            "failures": self.failures,
            "success_rate": round(self.success_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 3),
            "total_latency_ms": round(self.total_latency_ms, 3),
            "started_at": self.started_at.isoformat(),
            "by_tool": {
                name: {
                    "calls": b.calls,
                    "failures": b.failures,
                    "avg_latency_ms": round(b.avg_latency_ms, 3),
                    "total_latency_ms": round(b.total_latency_ms, 3),
                }
                for name, b in self.by_tool.items()
            },
        }


# ---------------------------------------------------------------------------
# Internal: JSON-safe coercion
# ---------------------------------------------------------------------------


def _json_safe(value: Any) -> Any:
    """Best-effort, dependency-free JSON coercion.

    The backend may be anything from an in-memory list to Mongo, so
    every model serializes its own fields via this helper. It:

    - converts datetime -> ISO string
    - converts Enum -> its value
    - walks dicts and lists recursively
    - falls back to ``str(...)`` for anything else

    It deliberately does *not* try to import pydantic or pymongo so
    ``models.py`` keeps zero runtime dependencies beyond stdlib.
    """
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    # dataclass with to_dict
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _json_safe(to_dict())
        except Exception:  # pragma: no cover
            pass
    return str(value)


__all__ = [
    "MCPOrigin",
    "MCPToolCall",
    "MCPToolResult",
    "MCPObservability",
]
