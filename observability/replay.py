"""``TraceReplayer`` + ``FailureAnalyzer`` — replay, debug, failure analysis.

Closes requirement #6 of the observability brief:

    replayable execution traces    TraceReplayer
    workflow debugging             TraceReplayer.step_through()
    orchestration introspection    FailureAnalyzer.introspect()
    failure analysis               FailureAnalyzer.hotspots()

Replay
------
We already persist everything needed: ``MCPRetrieval.replay(cid)``
returns a ``ReplayBundle`` with the memory record, OrchestrationTrace,
restored SwarmExecutionContext, provenance chain, and evidence
lookups. ``TraceReplayer`` is the observability-layer front-end
that rehydrates a run's events into an ``ExecutionTracer`` so the
full visualization + profiling stack can be pointed at a past run
without re-running the orchestrator.

Flow::

    replayer = TraceReplayer(client=MCPClient())
    tracer = replayer.replay(correlation_id)
    bundle = TraceVisualizer().render_all(tracer=tracer, ...)

Also supports ``step_through(correlation_id)`` which yields events
one-at-a-time with a configurable delay — the foundation the
cinematic player (commit 8) builds on.

Failure analysis
----------------
``FailureAnalyzer`` works against an ``ExecutionTracer`` (or a
``VerificationOutcome``) and groups error/warning events into
``FailureSummary`` records:

    by_validator    which engine emitted the failure
    by_rule_id      which named rule tripped
    by_agent        which agent was in play
    hotspots        top-N (validator, rule_id) pairs by count

Pure functions — no MCP calls. Reusable across replayed runs and
live runs.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generator

from observability.tracer import EventKind, ExecutionTracer

if TYPE_CHECKING:  # pragma: no cover
    from agents.verification.agent import VerificationOutcome
    from integrations.mcp.client import MCPClient
    from observability.tracer import ExecutionEvent


# ---------------------------------------------------------------------------
# TraceReplayer
# ---------------------------------------------------------------------------


@dataclass
class TraceReplayer:
    """Rehydrate past orchestration runs from MCP into a live tracer.

    Pass any ``MCPClient`` — the replayer uses ``MCPRetrieval.replay``
    internally and doesn't take a new dependency on Mongo or
    anything else. Works against the in-memory backend too.
    """

    client: "MCPClient"

    def __post_init__(self) -> None:
        from integrations.mcp.retrieval import MCPRetrieval

        self._retrieval = MCPRetrieval(client=self.client)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def replay(self, correlation_id: str) -> ExecutionTracer:
        """Rehydrate a past run as a populated ``ExecutionTracer``.

        Ingests in this order so the tracer sees events in the
        chronological order the run actually produced them:
            1. orchestration trace steps + activations
            2. provenance records → one VERIFICATION_EVENT each
               (validator=generating_agent, state derived from verdict)
            3. evidence records → one MCP_INTERACTION each

        Returns an empty tracer if the correlation_id has no records.
        """
        if not correlation_id:
            raise ValueError("replay requires a correlation_id")

        tracer = ExecutionTracer(correlation_id=correlation_id)
        bundle = self._retrieval.replay(correlation_id)
        if not bundle.lookup.exists:
            return tracer

        # Orchestration trace — rehydrate if the context snapshot
        # restored one.
        ctx = bundle.restore_context()
        if ctx is not None:
            tracer.ingest_orchestration_trace(
                getattr(ctx, "orchestration_trace", None)
            )

        # Provenance → verification events. The ProvenanceRecord
        # shape isn't a VerificationTrace so we convert with a
        # shim object that quacks enough for the tracer.
        for rec in bundle.lookup.provenance or []:
            tracer.ingest_verification_traces([_ProvRecordAdapter(rec)])

        # Evidence cache hits → MCP interaction events.
        for sid, doc in (bundle.evidence_by_source or {}).items():
            tracer.ingest_mcp_call(
                tool="evidence.get",
                success=True,
                latency_ms=0.0,
                correlation_id=correlation_id,
                details={"source_id": sid, "gene": doc.get("gene", "")},
            )

        return tracer

    def step_through(
        self, correlation_id: str, *, delay_s: float = 0.0
    ) -> Generator["ExecutionEvent", None, None]:
        """Yield events one-at-a-time with an optional pacing delay.

        Lets the cinematic player (commit 8) stream a past run as if
        it were live. Callers can also use it directly for
        debugger-style step-through inspection.
        """
        tracer = self.replay(correlation_id)
        for ev in tracer.events:
            yield ev
            if delay_s > 0:
                time.sleep(delay_s)


@dataclass
class _ProvRecordAdapter:
    """Adapter that makes a dict ProvenanceRecord look like a
    VerificationTrace to the tracer's ingest path."""

    record: dict[str, Any]

    @property
    def rule_id(self) -> str:
        return str(self.record.get("rule_id", ""))

    @property
    def correlation_id(self) -> str:
        return str(self.record.get("correlation_id", ""))

    @property
    def claim_id(self) -> str:
        return str(self.record.get("claim_id", ""))

    @property
    def validator(self) -> str:
        return str(self.record.get("generating_agent", "provenance_store"))

    @property
    def state(self) -> str:
        verdict = str(self.record.get("verification_verdict", "")).lower()
        if verdict in ("passed", "pass"):
            return "pass"
        if verdict in ("warning", "warn"):
            return "warn"
        if verdict in ("failed", "fail"):
            return "fail"
        return "pass"  # treat 'pending' / 'advisory' as pass for replay

    @property
    def confidence(self) -> float:
        try:
            return float(self.record.get("confidence") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @property
    def evidence_refs(self) -> list[str]:
        return list(self.record.get("evidence_sources") or [])

    @property
    def reason(self) -> str:
        return f"replayed from provenance_store ({self.rule_id})"

    @property
    def claim(self) -> str:
        return str(self.record.get("claim", ""))

    @property
    def created_at(self):
        # The tracer expects a datetime; fall back to now() if the
        # persisted ISO string can't be parsed.
        from datetime import datetime, timezone

        raw = self.record.get("recorded_at")
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                pass
        return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# FailureAnalyzer
# ---------------------------------------------------------------------------


@dataclass
class FailureSummary:
    """Aggregated view of error / warning events."""

    total_events: int = 0
    error_count: int = 0
    warning_count: int = 0
    by_validator: dict[str, int] = field(default_factory=dict)
    by_rule_id: dict[str, int] = field(default_factory=dict)
    by_agent: dict[str, int] = field(default_factory=dict)
    by_kind: dict[str, int] = field(default_factory=dict)
    hotspots: list[tuple[str, str, int]] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return self.error_count == 0 and self.warning_count == 0

    @property
    def failure_rate(self) -> float:
        if self.total_events == 0:
            return 0.0
        return round(self.error_count / self.total_events, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_events": self.total_events,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "failure_rate": self.failure_rate,
            "by_validator": dict(self.by_validator),
            "by_rule_id": dict(self.by_rule_id),
            "by_agent": dict(self.by_agent),
            "by_kind": dict(self.by_kind),
            "hotspots": list(self.hotspots),
            "is_clean": self.is_clean,
        }


@dataclass
class FailureAnalyzer:
    """Groups error/warning events into actionable summaries.

    Pure of external state. ``analyze(tracer)`` walks the tracer's
    event list; ``analyze_outcome(outcome)`` does the same for a
    ``VerificationOutcome``'s traces directly.
    """

    def analyze(self, tracer: ExecutionTracer) -> FailureSummary:
        """Produce a FailureSummary for a tracer's events."""
        summary = FailureSummary(total_events=tracer.count())
        bad_events = [
            e for e in tracer.events if e.status in ("error", "warning")
        ]

        by_validator: Counter[str] = Counter()
        by_rule: Counter[str] = Counter()
        by_agent: Counter[str] = Counter()
        by_kind: Counter[str] = Counter()
        pair_counter: Counter[tuple[str, str]] = Counter()

        for ev in bad_events:
            if ev.status == "error":
                summary.error_count += 1
            elif ev.status == "warning":
                summary.warning_count += 1

            validator = str(ev.payload.get("validator") or "")
            rule_id = ev.name
            agent = _derive_agent(ev)

            by_kind[ev.kind.value] += 1
            if validator:
                by_validator[validator] += 1
            if rule_id:
                by_rule[rule_id] += 1
            if agent:
                by_agent[agent] += 1
            if validator or rule_id:
                pair_counter[(validator or "—", rule_id or "—")] += 1

        summary.by_validator = dict(by_validator)
        summary.by_rule_id = dict(by_rule)
        summary.by_agent = dict(by_agent)
        summary.by_kind = dict(by_kind)
        # Top-10 hotspots as (validator, rule_id, count).
        summary.hotspots = [
            (v, r, c) for (v, r), c in pair_counter.most_common(10)
        ]
        return summary

    def analyze_outcome(
        self, outcome: "VerificationOutcome"
    ) -> FailureSummary:
        """Same analysis run directly against a VerificationOutcome.

        Builds a throwaway tracer from the outcome's traces so the
        analysis path is uniform.
        """
        tracer = ExecutionTracer(correlation_id=outcome.correlation_id)
        tracer.ingest_verification_traces(outcome.traces)
        return self.analyze(tracer)

    def introspect(self, tracer: ExecutionTracer) -> dict[str, Any]:
        """Convenience one-shot combining counts + hotspots.

        Shape is directly consumable by demo / dashboard print loops.
        """
        summary = self.analyze(tracer)
        return {
            "summary": summary.to_dict(),
            "kinds": tracer.summary(),
            "correlation_id": tracer.correlation_id,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_agent(ev: "ExecutionEvent") -> str:
    """Local copy of agent-derivation logic to avoid cross-module import."""
    payload = ev.payload or {}
    agent = payload.get("agent_id")
    if isinstance(agent, str) and agent:
        return agent
    called = payload.get("called_by")
    if isinstance(called, str) and called:
        return called
    if ":" in ev.name:
        return ev.name.split(":", 1)[1].strip()
    return ""


__all__ = [
    "TraceReplayer",
    "FailureAnalyzer",
    "FailureSummary",
]
