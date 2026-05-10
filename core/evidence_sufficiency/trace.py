"""``EvidenceSufficiencyTrace`` — frozen per-run sufficiency audit.

Phase 6, commit 16 of the Evidence Sufficiency Layer brief.
Closes requirement #22 directly — all seven tracked dimensions are
first-class fields, sorted and deduplicated where appropriate so
the trace is reproducible across runs.

Dimensions
----------

The brief (requirement #22) names seven things a sufficiency trace
must record:

    retrieved_evidence       the flat evidence-ref set the
                             sufficiency layer actually read
    graph_paths              KG path bundle (one entry per
                             ``GraphPath.to_dict()``), empty when
                             no bundle was supplied
    missing_hops             ordered list of coverage facets that
                             were MISSING or UNCERTAIN at the time
                             of the sufficiency decision
    uncertainty_transitions  ordered list of ``UncertaintyScore``
                             values the run passed through. One
                             entry per ``record_uncertainty(score)``
                             call — typically 1 (single checkpoint)
                             or 1..N (adaptive loop rounds)
    retrieval_loops          ordered list of retrieval-round
                             summaries — one per pass through the
                             ``AdaptiveRetrievalController``:
                             (round_index, strategies_used, stop_signal)
    sufficiency_decisions    ordered list of SufficiencyDecision
                             values the run passed through. Like
                             uncertainty_transitions but for the
                             7-value SufficiencyDecision enum.
    escalation_events        ordered list of escalation action
                             strings (e.g. 'REQUEST_MORE_EVIDENCE',
                             'ROUTE_TO_HUMAN_REVIEW'). Free-form
                             strings because the escalation vocabulary
                             lives in the orchestrator and the trace
                             is meant to be append-only.

Mutation discipline (frozen)
----------------------------

Same pattern as ``VerificationTrace`` and
``ClaimCoverageAnalysis`` — the record is immutable. To add an
event, call one of the ``record_*`` builder methods which return
a new trace preserving identity. The canonical pattern for a
callsite:

    trace = EvidenceSufficiencyTrace.empty(correlation_id=cid)
    trace = trace.record_retrieval_loop(round_index=0,
                                         strategies=(...),
                                         stop_signal="stop")
    trace = trace.record_sufficiency_decision(decision=...)

Serialization
-------------
``to_dict()`` is JSON-safe. Used by:
  - MCP persistence (phase-6 orchestrator wiring)
  - execution-tracer ingest (via a 'deterministic_rule' event kind,
    so the sufficiency checkpoint appears on the unified stream
    without extending the closed 7-value EventKind enum)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class RetrievalRoundRecord:
    """Frozen summary of one round of the adaptive retrieval loop.

    Matches the event surface the ``AdaptiveRetrievalController``
    already produces (``AdaptiveRetrievalOutcome.strategies_used`` +
    ``StopSignal``) — same vocabulary, so the trace can be built from
    an outcome without reformatting.
    """

    round_index: int
    strategies: tuple[str, ...]
    stop_signal: str  # 'stop' | 'fetch_more' | 'abort'

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "strategies": list(self.strategies),
            "stop_signal": self.stop_signal,
        }


@dataclass(frozen=True)
class EvidenceSufficiencyTrace:
    """Frozen, replay-safe per-run sufficiency audit record.

    Identity
    --------
    ``trace_id``       16-char hex, default-constructed uuid slice
    ``correlation_id`` MCP linkage to the orchestration run
    ``created_at``     ISO timestamp (UTC)
    """

    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    correlation_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Brief req #22 — the 7 tracked dimensions.
    retrieved_evidence: tuple[str, ...] = ()
    graph_paths: tuple[dict[str, Any], ...] = ()  # GraphPath.to_dict()
    missing_hops: tuple[str, ...] = ()  # facet.value strings
    uncertainty_transitions: tuple[str, ...] = ()  # UncertaintyScore.value
    retrieval_loops: tuple[RetrievalRoundRecord, ...] = ()
    sufficiency_decisions: tuple[str, ...] = ()  # SufficiencyDecision.value
    escalation_events: tuple[str, ...] = ()

    # ------------------------------------------------------------------
    # Empty factory
    # ------------------------------------------------------------------

    @classmethod
    def empty(cls, *, correlation_id: str = "") -> EvidenceSufficiencyTrace:
        """Fresh trace for a new run."""

        return cls(correlation_id=correlation_id)

    # ------------------------------------------------------------------
    # Record builders — each returns a new trace preserving identity
    # ------------------------------------------------------------------

    def record_evidence(self, refs: tuple[str, ...]) -> EvidenceSufficiencyTrace:
        """Append evidence ids; dedup against what's already recorded.

        Stable ordering: existing refs retain their order; new refs
        are appended in the order supplied, with duplicates dropped.
        """

        if not refs:
            return self
        seen = set(self.retrieved_evidence)
        new = []
        for r in refs:
            r_str = str(r)
            if not r_str or r_str in seen:
                continue
            seen.add(r_str)
            new.append(r_str)
        if not new:
            return self
        return replace(self, retrieved_evidence=self.retrieved_evidence + tuple(new))

    def record_graph_paths(self, paths: tuple[dict[str, Any], ...]) -> EvidenceSufficiencyTrace:
        """Append serialized GraphPath dicts. No dedup — paths are ordered."""

        if not paths:
            return self
        return replace(self, graph_paths=self.graph_paths + tuple(paths))

    def record_missing_hops(self, hops: tuple[str, ...]) -> EvidenceSufficiencyTrace:
        """Replace missing_hops — this is a snapshot, not an accumulation.

        Rationale: missing hops are the STATE at the point the sufficiency
        decision is emitted, not a history. Successive decisions in the
        same run (e.g. after adaptive retrieval) overwrite rather than
        append.
        """

        return replace(self, missing_hops=tuple(hops))

    def record_uncertainty(self, score_value: str) -> EvidenceSufficiencyTrace:
        """Append an uncertainty tier to the transition history."""

        if not score_value:
            return self
        return replace(
            self,
            uncertainty_transitions=(*self.uncertainty_transitions, score_value),
        )

    def record_retrieval_loop(
        self,
        *,
        round_index: int,
        strategies: tuple[str, ...],
        stop_signal: str,
    ) -> EvidenceSufficiencyTrace:
        """Append one retrieval-round summary."""

        entry = RetrievalRoundRecord(
            round_index=int(round_index),
            strategies=tuple(str(s) for s in strategies),
            stop_signal=str(stop_signal),
        )
        return replace(self, retrieval_loops=(*self.retrieval_loops, entry))

    def record_sufficiency_decision(self, decision_value: str) -> EvidenceSufficiencyTrace:
        """Append a sufficiency decision to the decision history."""

        if not decision_value:
            return self
        return replace(
            self,
            sufficiency_decisions=(*self.sufficiency_decisions, decision_value),
        )

    def record_escalation(self, action: str) -> EvidenceSufficiencyTrace:
        """Append an escalation-action label (free-form string)."""

        if not action:
            return self
        return replace(self, escalation_events=(*self.escalation_events, str(action)))

    # ------------------------------------------------------------------
    # Derived / helpers
    # ------------------------------------------------------------------

    @property
    def is_empty(self) -> bool:
        """True iff no dimension has been recorded yet."""

        return (
            not self.retrieved_evidence
            and not self.graph_paths
            and not self.missing_hops
            and not self.uncertainty_transitions
            and not self.retrieval_loops
            and not self.sufficiency_decisions
            and not self.escalation_events
        )

    @property
    def rounds_completed(self) -> int:
        """Convenience — length of retrieval_loops."""

        return len(self.retrieval_loops)

    @property
    def final_decision(self) -> str:
        """Last decision recorded, or empty string if none."""

        return self.sufficiency_decisions[-1] if self.sufficiency_decisions else ""

    @property
    def final_uncertainty(self) -> str:
        """Last uncertainty tier recorded, or empty string if none."""

        return self.uncertainty_transitions[-1] if self.uncertainty_transitions else ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at.isoformat(),
            "retrieved_evidence": list(self.retrieved_evidence),
            "graph_paths": [dict(p) for p in self.graph_paths],
            "missing_hops": list(self.missing_hops),
            "uncertainty_transitions": list(self.uncertainty_transitions),
            "retrieval_loops": [r.to_dict() for r in self.retrieval_loops],
            "sufficiency_decisions": list(self.sufficiency_decisions),
            "escalation_events": list(self.escalation_events),
            "is_empty": self.is_empty,
            "rounds_completed": self.rounds_completed,
            "final_decision": self.final_decision,
            "final_uncertainty": self.final_uncertainty,
        }


__all__ = [
    "EvidenceSufficiencyTrace",
    "RetrievalRoundRecord",
]
