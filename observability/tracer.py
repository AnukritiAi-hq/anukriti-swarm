"""``ExecutionTracer`` — unified event stream across the whole swarm.

Closes requirement #3 of the observability brief (track 7 event
kinds) and the foundation of req #6 (replayable traces).

The existing system records orchestration events in three separate
places:

    core.orchestrator.trace.OrchestrationTrace     step + activation timeline
    integrations.mcp.models.MCPObservability       per-tool call metrics
    core.verification.trace.VerificationTrace      per-claim safety events

That's the right layering for each concern — but debugging a run
means correlating all three. ``ExecutionTracer`` is the correlation
seam: one method ingests any of the three source types, produces a
uniform ``ExecutionEvent`` stream, and exposes filter/search helpers.

Event kinds (the 7 the brief names)
-----------------------------------

    AGENT_ACTIVATION       router picked a specialist agent
    ROUTING_DECISION       planner/router emitted a decision
    EVIDENCE_RETRIEVAL     retrieval agent returned a passage
    VERIFICATION_EVENT     a verification check ran (pass/fail/warn)
    MCP_INTERACTION        any MCP tool invocation
    GEMINI_STEP            LLM-originated step (origin='generative')
    DETERMINISTIC_RULE     pure-rule step (origin='deterministic')

Each event carries:
    kind, name, origin, timestamp, duration_ms, status, source_type
    payload  (discriminator-specific dict: e.g. MCP events carry the
              tool name + latency; verification events carry the
              check_name + verdict; activation events carry the
              agent_id + reason)

Subscribers
-----------
Pass a callable to ``on_event`` to receive events as they're
ingested — lets the cinematic player stream a run in real time
and lets the activity monitor + profiler update live.

Design notes
------------
- ExecutionTracer is stateful (holds the event list) but
  thread-unsafe. One instance per run. Construction is zero-arg.
- Ingesting an already-ingested trace is idempotent on event_id
  so callers can safely re-ingest after MCP persistence.
- Events are frozen dataclasses so the tracer's public list
  is safe to hand to consumers without defensive copies.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Iterable


class EventKind(str, Enum):
    """The 7 event kinds the brief names in req #3."""

    AGENT_ACTIVATION = "agent_activation"
    ROUTING_DECISION = "routing_decision"
    EVIDENCE_RETRIEVAL = "evidence_retrieval"
    VERIFICATION_EVENT = "verification_event"
    MCP_INTERACTION = "mcp_interaction"
    GEMINI_STEP = "gemini_step"
    DETERMINISTIC_RULE = "deterministic_rule"


# Origin matches the existing trace module's Literal.
EventOrigin = str  # 'deterministic' | 'generative' | 'system'


@dataclass(frozen=True)
class ExecutionEvent:
    """One ingested event on the unified stream."""

    event_id: str
    kind: EventKind
    name: str
    origin: EventOrigin
    status: str                 # 'success' | 'warning' | 'error' | 'pending'
    duration_ms: float
    timestamp: datetime
    source_type: str            # which ingest path produced this ('step',
                                # 'activation', 'mcp', 'verification')
    correlation_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind.value,
            "name": self.name,
            "origin": self.origin,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "source_type": self.source_type,
            "correlation_id": self.correlation_id,
            "payload": dict(self.payload),
        }


# Subscriber signature.
EventHandler = Callable[[ExecutionEvent], None]


# ---------------------------------------------------------------------------
# Tracer
# ---------------------------------------------------------------------------


@dataclass
class ExecutionTracer:
    """Unified event stream across the full orchestration lifecycle.

    Usage:
        tracer = ExecutionTracer()
        tracer.ingest_orchestration_trace(result.context.orchestration_trace)
        tracer.ingest_mcp_snapshot(client.snapshot())
        tracer.ingest_verification_traces(outcome.traces)

        for ev in tracer.events_by_kind(EventKind.VERIFICATION_EVENT):
            print(ev.name, ev.status)
    """

    correlation_id: str = ""
    _events: list[ExecutionEvent] = field(default_factory=list)
    _seen_ids: set[str] = field(default_factory=set)
    _subscribers: list[EventHandler] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def on_event(self, handler: EventHandler) -> None:
        """Register a callback invoked on every newly-ingested event."""
        self._subscribers.append(handler)

    # ------------------------------------------------------------------
    # Ingest paths
    # ------------------------------------------------------------------

    def ingest_orchestration_trace(self, trace: Any) -> int:
        """Ingest steps + activations from ``OrchestrationTrace``.

        Returns the number of *new* events added (idempotent on
        re-ingest).
        """
        if trace is None:
            return 0
        added = 0
        cid = getattr(trace, "correlation_id", self.correlation_id) or self.correlation_id
        # Steps → DETERMINISTIC_RULE or GEMINI_STEP depending on origin.
        for step in getattr(trace, "steps", []) or []:
            kind = (
                EventKind.GEMINI_STEP
                if getattr(step, "origin", "") == "generative"
                else EventKind.DETERMINISTIC_RULE
            )
            # 'memory.consult' is technically a system step but it's
            # a key lifecycle moment — surface it as a routing
            # decision so graphs show the orchestrator consulting
            # memory before planning.
            if getattr(step, "name", "") == "memory.consult":
                kind = EventKind.ROUTING_DECISION

            added += self._append(
                ExecutionEvent(
                    event_id=f"step_{cid}_{step.step}",
                    kind=kind,
                    name=step.name,
                    origin=step.origin,
                    status=step.status,
                    duration_ms=float(step.duration_ms or 0.0),
                    timestamp=step.started_at,
                    source_type="step",
                    correlation_id=cid,
                    payload={"details": dict(step.details or {}), "step_number": step.step},
                )
            )
        # Activations → AGENT_ACTIVATION.
        for i, act in enumerate(getattr(trace, "activations", []) or []):
            added += self._append(
                ExecutionEvent(
                    event_id=f"act_{cid}_{i}",
                    kind=EventKind.AGENT_ACTIVATION,
                    name=f"activate:{act.agent_id}",
                    origin="deterministic",
                    status="success",
                    duration_ms=0.0,
                    timestamp=act.activated_at,
                    source_type="activation",
                    correlation_id=cid,
                    payload={
                        "agent_id": act.agent_id,
                        "role": act.role,
                        "reason": act.reason,
                    },
                )
            )
        return added

    def ingest_mcp_snapshot(self, snapshot: dict[str, Any]) -> int:
        """Ingest the observability rollup from ``MCPClient.snapshot()``.

        Produces one MCP_INTERACTION event per tool name (the snapshot
        is aggregated by tool; individual call records live in the
        registry's audit collection if the caller wants those).
        """
        if not snapshot:
            return 0
        added = 0
        cid = self.correlation_id or snapshot.get("correlation_id", "")
        for tool_name, stats in (snapshot.get("by_tool") or {}).items():
            calls = int(stats.get("calls", 0))
            failures = int(stats.get("failures", 0))
            status = "success" if failures == 0 else ("warning" if failures < calls else "error")
            added += self._append(
                ExecutionEvent(
                    event_id=f"mcp_{cid}_{tool_name}",
                    kind=EventKind.MCP_INTERACTION,
                    name=tool_name,
                    origin="system",
                    status=status,
                    duration_ms=float(stats.get("avg_latency_ms", 0.0)) * calls,
                    timestamp=datetime.now(timezone.utc),
                    source_type="mcp",
                    correlation_id=cid,
                    payload={
                        "tool": tool_name,
                        "calls": calls,
                        "failures": failures,
                        "avg_latency_ms": float(stats.get("avg_latency_ms", 0.0)),
                    },
                )
            )
        return added

    def ingest_mcp_call(
        self, *, tool: str, success: bool, latency_ms: float,
        correlation_id: str = "", details: dict[str, Any] | None = None,
    ) -> int:
        """Ingest a single MCP tool call (for tests + live streaming)."""
        return self._append(
            ExecutionEvent(
                event_id=f"mcp_{correlation_id or self.correlation_id}_{tool}_{uuid.uuid4().hex[:6]}",
                kind=EventKind.MCP_INTERACTION,
                name=tool,
                origin="system",
                status="success" if success else "error",
                duration_ms=latency_ms,
                timestamp=datetime.now(timezone.utc),
                source_type="mcp_single",
                correlation_id=correlation_id or self.correlation_id,
                payload=dict(details or {}),
            )
        )

    def ingest_verification_traces(self, traces: Iterable[Any]) -> int:
        """Ingest ``VerificationTrace`` records.

        Retrieval traces (rule_id starts with ``evidence.``) are
        mapped to EVIDENCE_RETRIEVAL; everything else is a
        VERIFICATION_EVENT.
        """
        added = 0
        for i, tr in enumerate(traces or []):
            rule_id = getattr(tr, "rule_id", "") or ""
            kind = (
                EventKind.EVIDENCE_RETRIEVAL
                if rule_id.startswith("evidence.")
                else EventKind.VERIFICATION_EVENT
            )
            cid = getattr(tr, "correlation_id", "") or self.correlation_id
            added += self._append(
                ExecutionEvent(
                    event_id=f"verif_{cid}_{getattr(tr, 'claim_id', i)}",
                    kind=kind,
                    name=rule_id or f"verification_{i}",
                    origin="deterministic",
                    status=_verification_status(tr),
                    duration_ms=0.0,
                    timestamp=getattr(tr, "created_at", datetime.now(timezone.utc)),
                    source_type="verification",
                    correlation_id=cid,
                    payload={
                        "validator": getattr(tr, "validator", ""),
                        "state": getattr(tr, "state", ""),
                        "confidence": float(getattr(tr, "confidence", 0.0)),
                        "evidence_refs": list(getattr(tr, "evidence_refs", []) or []),
                        "reason": getattr(tr, "reason", ""),
                        "claim": getattr(tr, "claim", "")[:120],
                    },
                )
            )
        return added

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def events(self) -> list[ExecutionEvent]:
        """Defensive-copied chronological event list."""
        return sorted(self._events, key=lambda e: e.timestamp)

    def events_by_kind(self, kind: EventKind) -> list[ExecutionEvent]:
        return [e for e in self._events if e.kind == kind]

    def events_by_status(self, status: str) -> list[ExecutionEvent]:
        return [e for e in self._events if e.status == status]

    def count(self) -> int:
        return len(self._events)

    def summary(self) -> dict[str, int]:
        """Count of events per kind — useful one-liner for demos."""
        out: dict[str, int] = {}
        for e in self._events:
            out[e.kind.value] = out.get(e.kind.value, 0) + 1
        return out

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _append(self, event: ExecutionEvent) -> int:
        """Insert ``event`` if unseen; fan out to subscribers. Returns 0 or 1."""
        if event.event_id in self._seen_ids:
            return 0
        self._seen_ids.add(event.event_id)
        self._events.append(event)
        for sub in self._subscribers:
            try:
                sub(event)
            except Exception:
                # A broken subscriber must not take the tracer down;
                # we'd rather keep ingesting and let higher-level
                # logs surface the bug.
                pass
        return 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _verification_status(trace: Any) -> str:
    """Map VerificationTrace.state → ExecutionEvent.status."""
    state = getattr(trace, "state", "")
    if state == "pass":
        return "success"
    if state == "warn":
        return "warning"
    if state == "fail":
        return "error"
    return "pending"


__all__ = [
    "ExecutionTracer",
    "ExecutionEvent",
    "EventKind",
    "EventHandler",
]
