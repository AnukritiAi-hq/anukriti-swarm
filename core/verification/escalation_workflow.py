"""``EscalationWorkflow`` — active actions when verification fails.

Closes requirement #7 of the safety brief. The brief lists four
escalation actions the system must take when verification detects
a problem:

    reroute              send the work to a specialist agent
                         (usually a narrower pharmacogene agent or
                          a retrieval re-run with a different query)
    request_evidence     ask the retrieval layer to re-search for
                         a specific source_id that went missing
    downgrade            lower the confidence of a downstream
                         recommendation so the audience templates
                         render with extra caveats
    block                refuse to surface the output entirely

Today, individual engines already *emit* EscalationEvent instances
on their traces. What was missing is a single module that
**decides** which action to take for a given VerificationOutcome
and **routes** that decision into concrete results the orchestrator
can consume.

Separation of concerns:

    - Engines (claim_validator, grounding, safety, provenance)
      decide *what* went wrong and attach raw EscalationEvents.
    - EscalationWorkflow decides *what to do about it* — mapping
      from (tier, decision.block, grounding coverage, missing
      evidence list, …) onto a concrete EscalationPlan.
    - The orchestrator / demo consumes the plan to produce the
      user-visible behaviour: a blocked reply, a caveated
      narrative, a retry.

Contract
--------
``EscalationWorkflow.plan(outcome)`` returns an ``EscalationPlan``
listing every action the system should take. Always returns a
plan — a clean run gets an empty plan with ``status='none'``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agents.verification.agent import VerificationOutcome
from core.verification.scoring import VerificationTier
from core.verification.trace import VerificationTrace


class EscalationAction(str, Enum):
    """The four action kinds the brief names (req #7)."""

    REROUTE = "reroute"
    REQUEST_EVIDENCE = "request_evidence"
    DOWNGRADE = "downgrade"
    BLOCK = "block"


@dataclass(frozen=True)
class EscalationStep:
    """One concrete action the orchestrator can execute.

    Every field is a primitive string so the plan round-trips through
    MCP persistence / JSON dashboards without special handling.
    """

    action: EscalationAction
    target: str          # agent id, retrieval source_id, or "*" for global
    reason: str
    severity: str        # "info" | "warning" | "critical"
    origin_claim_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "target": self.target,
            "reason": self.reason,
            "severity": self.severity,
            "origin_claim_id": self.origin_claim_id,
        }


@dataclass
class EscalationPlan:
    """Aggregate plan of every escalation the workflow decided on.

    ``status`` is a single-word summary the demo prints:
        'none'     no escalations, delivery proceeds clean
        'mitigated' warn-level escalations only (downgrade,
                    request_evidence); delivery proceeds with caveats
        'blocked'   at least one block-action fired; delivery refused
    """

    status: str = "none"
    steps: list[EscalationStep] = field(default_factory=list)

    @property
    def is_blocked(self) -> bool:
        return any(s.action == EscalationAction.BLOCK for s in self.steps)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "is_blocked": self.is_blocked,
            "step_count": len(self.steps),
            "steps": [s.to_dict() for s in self.steps],
        }


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


@dataclass
class EscalationWorkflow:
    """Decide concrete escalation actions from a VerificationOutcome.

    Stateless. One instance reuses across many outcomes.

    Parameters
    ----------
    grounding_coverage_floor:
        If ``outcome.grounding.coverage`` falls below this, a
        ``request_evidence`` action fires for each missing source.
        Default 0.5 — below half-coverage we actively ask the
        retrieval layer to search again.
    downgrade_on_partial:
        When True (default), partially_grounded outcomes emit a
        DOWNGRADE step pointing at the narrative layer so audience
        templates render with "partial grounding" caveats.
    """

    grounding_coverage_floor: float = 0.5
    downgrade_on_partial: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(self, outcome: VerificationOutcome) -> EscalationPlan:
        """Produce the EscalationPlan for an outcome."""
        steps: list[EscalationStep] = []

        # Rule 1 — hard block when the safety decision says block.
        # This is the strongest signal; everything else is advisory
        # next to it.
        if outcome.decision and outcome.decision.block:
            steps.append(
                EscalationStep(
                    action=EscalationAction.BLOCK,
                    target="narrative_layer",
                    reason=(
                        f"Safety decision {outcome.decision.tier.value}: "
                        f"{outcome.decision.reason}"
                    ),
                    severity="critical",
                )
            )

        # Rule 2 — reroute on an unverified / unknown-allele path.
        # Unverified means "we couldn't attest" — a specialist agent
        # might have the data we're missing.
        if outcome.decision and outcome.decision.tier == VerificationTier.UNVERIFIED:
            steps.append(
                EscalationStep(
                    action=EscalationAction.REROUTE,
                    target=self._reroute_target(outcome),
                    reason=(
                        f"Verification unverified: {outcome.decision.reason}"
                    ),
                    severity="warning",
                )
            )

        # Rule 3 — request_evidence for every missing source id.
        # Preferred over a hard failure — lets the retrieval layer
        # top up the evidence cache and we can try again.
        if outcome.grounding and outcome.grounding.missing_source_ids:
            coverage = outcome.grounding.coverage
            if coverage < self.grounding_coverage_floor or outcome.decision.block:
                # Low coverage or already-blocking safety → escalate.
                # Otherwise we silently degrade (the warning already
                # fired).
                for sid in outcome.grounding.missing_source_ids:
                    steps.append(
                        EscalationStep(
                            action=EscalationAction.REQUEST_EVIDENCE,
                            target=sid,
                            reason=(
                                f"Source {sid!r} cited but not indexed in MCP "
                                f"evidence cache (coverage={coverage:.0%})"
                            ),
                            severity="warning",
                        )
                    )

        # Rule 4 — downgrade on PARTIALLY_GROUNDED. Confidence drops
        # from "deliver clean" to "deliver with caveats".
        if (
            self.downgrade_on_partial
            and outcome.decision
            and outcome.decision.tier == VerificationTier.PARTIALLY_GROUNDED
        ):
            steps.append(
                EscalationStep(
                    action=EscalationAction.DOWNGRADE,
                    target="narrative_layer",
                    reason=(
                        f"Partially grounded ({outcome.decision.reason}). "
                        "Render with caveats."
                    ),
                    severity="info",
                )
            )

        # Rule 5 — per-claim escalations bubble up from engine traces.
        # The engines already attached EscalationEvents; we surface
        # any that aren't already covered by the aggregate rules
        # above so they're not lost.
        for tr in outcome.traces:
            for ev in tr.escalation_events:
                # Skip if we already emitted a step for this action/target.
                if any(
                    s.action.value == ev.action and s.target == ev.target
                    for s in steps
                ):
                    continue
                try:
                    action = EscalationAction(ev.action)
                except ValueError:
                    # Unknown action string — preserve verbatim for
                    # audit but don't fail the workflow.
                    continue
                steps.append(
                    EscalationStep(
                        action=action,
                        target=ev.target or self._reroute_target(outcome),
                        reason=ev.reason,
                        severity="warning",
                        origin_claim_id=tr.claim_id,
                    )
                )

        status = self._summarise_status(steps)
        return EscalationPlan(status=status, steps=steps)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _reroute_target(outcome: VerificationOutcome) -> str:
        """Pick a sensible reroute target based on the failing trace."""
        # Prefer the specialist agent the offending trace named.
        for tr in outcome.traces:
            if tr.failed and tr.generating_agent:
                # Avoid pointing back at the safety engine itself.
                if "safety" not in tr.generating_agent.lower():
                    return tr.generating_agent
        return "pharmacogene_specialist"

    @staticmethod
    def _summarise_status(steps: list[EscalationStep]) -> str:
        if not steps:
            return "none"
        if any(s.action == EscalationAction.BLOCK for s in steps):
            return "blocked"
        return "mitigated"


# ---------------------------------------------------------------------------
# Annotating traces with the plan
# ---------------------------------------------------------------------------


def annotate_traces(
    traces: list[VerificationTrace], plan: EscalationPlan
) -> list[VerificationTrace]:
    """Return new traces with plan steps attached as EscalationEvents.

    Convenience for callers who want to persist the plan *through* the
    trace list (e.g. pipe straight into ``MCPProvenanceStore``). Each
    trace receives events whose ``origin_claim_id`` matches — plus
    any "global" (no origin_claim_id) events get attached to every
    failing trace so at least one record carries the escalation.
    """
    from core.verification.trace import EscalationEvent

    # Bucket steps by origin claim id.
    by_origin: dict[str, list[EscalationStep]] = {}
    globals_: list[EscalationStep] = []
    for step in plan.steps:
        if step.origin_claim_id:
            by_origin.setdefault(step.origin_claim_id, []).append(step)
        else:
            globals_.append(step)

    out: list[VerificationTrace] = []
    # Attach any-origin steps to the first failing trace if no
    # better match is available, so the audit record isn't silently
    # lost.
    first_fail_claim_id = next(
        (t.claim_id for t in traces if t.failed), ""
    )

    for tr in traces:
        events = list(tr.escalation_events)
        for step in by_origin.get(tr.claim_id, []):
            events.append(
                EscalationEvent(
                    action=step.action.value,
                    reason=step.reason,
                    target=step.target,
                )
            )
        if tr.claim_id == first_fail_claim_id:
            for step in globals_:
                events.append(
                    EscalationEvent(
                        action=step.action.value,
                        reason=step.reason,
                        target=step.target,
                    )
                )
        out.append(
            tr if events == list(tr.escalation_events)
            else _rebuild_with_events(tr, tuple(events))
        )
    return out


def _rebuild_with_events(
    tr: VerificationTrace, events: tuple
) -> VerificationTrace:
    """Return a new trace identical to ``tr`` but with new escalation_events."""
    from core.verification.trace import make_trace

    return make_trace(
        claim=tr.claim,
        validator=tr.validator,
        state=tr.state,
        confidence=tr.confidence,
        evidence_refs=tr.evidence_refs,
        escalation_events=events,
        tier=tr.tier,
        reason=tr.reason,
        correlation_id=tr.correlation_id,
        generating_agent=tr.generating_agent,
        rule_id=tr.rule_id,
        claim_id=tr.claim_id,
    )


__all__ = [
    "EscalationWorkflow",
    "EscalationPlan",
    "EscalationStep",
    "EscalationAction",
    "annotate_traces",
]
