"""``VerificationTrace`` — per-claim audit record.

Requirement #9 of the deterministic safety brief: every validated
biomedical claim produces a ``VerificationTrace`` containing exactly
the six fields the brief names:

    claim              the biomedical statement being validated
                       (e.g. "CYP2C19 *2/*2 → Poor Metabolizer")
    validator          which engine produced this trace
                       (e.g. "BiomedicalClaimValidator",
                        "EvidenceGroundingEngine",
                        "SafetyConstraintEngine",
                        "ProvenanceValidator")
    evidence_refs      list of source IDs (PMIDs, CPIC guideline IDs)
                       the validator looked up or relied on
    state              pass / fail / warn outcome
    confidence         numeric confidence the validator assigns
                       (propagated from upstream stages, [0.0, 1.0])
    escalation_events  list of escalation actions that fired as a
                       result of this validation (may be empty)

Additional optional fields give the trace enough context to survive
MCP persistence and later replay without losing information:

    tier               the 5-tier score (nice to have alongside
                       pass/fail — the tier is richer)
    reason             human-readable explanation
    claim_id           stable identifier matching MCP
                       ``ProvenanceRecord.claim_id`` when the claim
                       was also persisted into the provenance store
    correlation_id     orchestration run this trace belongs to
    generating_agent   which agent produced the *claim* (orthogonal
                       to ``validator`` which produced the *trace*)
    rule_id            deterministic rule the claim derives from
                       (e.g. "cpic.activity_score", "hardy_weinberg")
    created_at         ISO timestamp

Design
------
The trace is a **frozen** dataclass — once a claim is validated,
its verdict is part of the audit trail and must not be mutated.
Downstream processes that want to annotate a trace produce a new
trace with the annotation appended to ``escalation_events``.

``to_dict()`` produces a JSON-safe form identical in shape to
what an ``MCPProvenanceStore.ProvenanceRecord`` exposes — by
intent. A ``BiomedicalClaimValidator`` that returns traces can
pipe them straight into ``MCPProvenanceStore.record()`` without
any reshaping. The linkage field is ``claim_id`` which is shared
across both systems.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.verification.scoring import VerificationTier


# The brief names the field "pass/fail state"; we use these canonical
# tokens so it round-trips cleanly through dicts / JSON / Mongo.
#
# ``state`` is independent of ``tier``:
#   state=pass + tier=grounded            → delivered clean
#   state=pass + tier=partially_grounded  → delivered with caveats
#   state=fail + tier=unverified          → escalation triggered
#   state=fail + tier=unsafe              → hard block
#
# ``state`` answers "did this validator accept the claim?"; ``tier``
# answers "how safe is the claim overall?". Both are preserved.
TraceState = str  # "pass" | "fail" | "warn"

_VALID_STATES: frozenset[str] = frozenset({"pass", "fail", "warn"})


@dataclass(frozen=True)
class EscalationEvent:
    """One escalation action triggered while validating a claim.

    The ``EscalationWorkflow`` (commit 9) produces these when a
    validator returns fail/warn. Every event is attached to a trace
    so the audit report can answer "what did the system do when
    claim X failed?".
    """

    action: str          # "reroute" | "request_evidence" | "downgrade" | "block"
    reason: str
    target: str = ""     # agent / engine / source id the action points at
    triggered_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "target": self.target,
            "triggered_at": self.triggered_at.isoformat(),
        }


@dataclass(frozen=True)
class VerificationTrace:
    """Per-claim audit trace — see module docstring for the 6 required fields."""

    # --- the six fields the brief names (req #9) ---
    claim: str
    validator: str
    evidence_refs: tuple[str, ...]
    state: TraceState            # "pass" / "fail" / "warn"
    confidence: float
    escalation_events: tuple[EscalationEvent, ...]

    # --- useful context for replay / audit ---
    tier: VerificationTier | None = None
    reason: str = ""
    claim_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    correlation_id: str = ""
    generating_agent: str = ""
    rule_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        # Defensive: reject meaningless states so a bad caller can't
        # pollute the audit trail with unknown tokens. Because the
        # dataclass is frozen we use object.__setattr__ sparingly
        # only for normalization.
        if self.state not in _VALID_STATES:
            raise ValueError(
                f"VerificationTrace.state must be one of "
                f"{sorted(_VALID_STATES)}, got {self.state!r}"
            )
        # Clamp confidence into [0.0, 1.0] — downstream consumers
        # rely on this invariant for propagation math.
        if self.confidence < 0.0 or self.confidence > 1.0:
            object.__setattr__(
                self, "confidence", max(0.0, min(1.0, self.confidence))
            )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def passed(self) -> bool:
        return self.state == "pass"

    @property
    def failed(self) -> bool:
        return self.state == "fail"

    @property
    def warned(self) -> bool:
        return self.state == "warn"

    def with_escalation(self, event: EscalationEvent) -> "VerificationTrace":
        """Return a new trace with ``event`` appended to escalation_events.

        Frozen dataclass idiom — callers never mutate an existing trace.
        """
        return VerificationTrace(
            claim=self.claim,
            validator=self.validator,
            evidence_refs=self.evidence_refs,
            state=self.state,
            confidence=self.confidence,
            escalation_events=self.escalation_events + (event,),
            tier=self.tier,
            reason=self.reason,
            claim_id=self.claim_id,
            correlation_id=self.correlation_id,
            generating_agent=self.generating_agent,
            rule_id=self.rule_id,
            created_at=self.created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dict form, shaped compatibly with MCP ProvenanceRecord.

        Matches the key set ``MCPProvenanceStore`` already persists
        (``claim_id``, ``claim``, ``generating_agent``, ``rule_id``,
        ``correlation_id``, ``evidence_sources``, ``verification_verdict``,
        ``confidence``) plus a few safety-engine additions.
        """
        return {
            # --- the six fields the brief names ---
            "claim": self.claim,
            "validator": self.validator,
            "evidence_refs": list(self.evidence_refs),
            "state": self.state,
            "confidence": self.confidence,
            "escalation_events": [e.to_dict() for e in self.escalation_events],
            # --- context / MCP linkage ---
            "tier": self.tier.value if self.tier is not None else "",
            "reason": self.reason,
            "claim_id": self.claim_id,
            "correlation_id": self.correlation_id,
            "generating_agent": self.generating_agent,
            "rule_id": self.rule_id,
            "created_at": self.created_at.isoformat(),
            # --- aliases so ProvenanceStore.record(**dict) works if a
            #     caller wants to persist the trace as a provenance
            #     record without reshaping. These duplicate the
            #     ``evidence_refs`` + ``state`` data under the names
            #     ``MCPProvenanceStore`` expects. ---
            "evidence_sources": list(self.evidence_refs),
            "verification_verdict": self.state,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_trace(
    *,
    claim: str,
    validator: str,
    state: TraceState,
    confidence: float = 1.0,
    evidence_refs: tuple[str, ...] | list[str] = (),
    escalation_events: tuple[EscalationEvent, ...] | list[EscalationEvent] = (),
    tier: VerificationTier | None = None,
    reason: str = "",
    correlation_id: str = "",
    generating_agent: str = "",
    rule_id: str = "",
    claim_id: str = "",
) -> VerificationTrace:
    """Ergonomic factory — accepts lists and tuples, fills optional fields.

    Code that builds traces in a tight loop (e.g. the
    ``BiomedicalClaimValidator``) finds this more convenient than
    passing a full constructor call. Doesn't change any semantics.
    """
    return VerificationTrace(
        claim=claim,
        validator=validator,
        evidence_refs=tuple(evidence_refs),
        state=state,
        confidence=confidence,
        escalation_events=tuple(escalation_events),
        tier=tier,
        reason=reason,
        correlation_id=correlation_id,
        generating_agent=generating_agent,
        rule_id=rule_id,
        claim_id=claim_id or uuid.uuid4().hex[:16],
    )


__all__ = [
    "VerificationTrace",
    "EscalationEvent",
    "TraceState",
    "make_trace",
]
