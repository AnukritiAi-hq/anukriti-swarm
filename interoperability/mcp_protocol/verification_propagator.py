"""``VerificationStatePropagator`` — lifts safety-engine state onto envelopes.

Closes the verification piece of requirement #2 of the
interoperability brief.

Bridges the session-2 safety engine (``agents.verification`` +
``core.verification``) into the interoperability message stream.
For each envelope that carries a claim requiring verification:

  1. **Lifts**     safety-engine ``VerificationOutcome`` onto the
                   envelope's ``verification_state`` +
                   ``confidence_level`` + ``confidence_value`` so
                   the AgentMessageBus's safety gate can block or
                   route correctly.
  2. **Propagates** per-claim safety signals into
                   ``SharedBiomedicalContext.verification_graph``
                   when a context + protocol are wired.
  3. **Escalates** a ``FAILED`` outcome into a bus-level block
                   (envelope stays FAILED, bus's safety_gate
                   intercepts delivery).

Does NOT:
  - Re-run the safety engine — only lifts outcomes onto envelopes.
  - Weaken the bus's safety gate — FAILED stays FAILED.
  - Touch non-genomic envelopes.

Two entry points:

    lift(envelope, outcome)            imperative — most common
    lift_with_agent(envelope, agent,   runs the safety agent
                    run_dict)          inline and lifts result

Optional ``context_protocol`` kwarg — when passed, the propagator
also adds ``VerificationNode`` records to the shared context graph
for each per-claim trace in the outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from interoperability.shared_context.biomedical import VerificationNode
from interoperability.shared_context.envelope import (
    AgentContextEnvelope,
    ConfidenceLevel,
    VerificationState,
)

if TYPE_CHECKING:  # pragma: no cover
    from agents.verification.agent import (
        BiomedicalVerificationAgent,
        VerificationOutcome,
    )
    from interoperability.shared_context.protocol import SwarmContextProtocol


# Map tier -> VerificationState. Keeps the propagator independent
# of the exact safety-engine enum at import time.
_TIER_TO_STATE: dict[str, VerificationState] = {
    "grounded": VerificationState.PASSED,
    "partially_grounded": VerificationState.WARNING,
    "unverified": VerificationState.WARNING,
    "conflicting": VerificationState.FAILED,
    "unsafe": VerificationState.FAILED,
}


def _confidence_level_for(value: float) -> ConfidenceLevel:
    """Numeric confidence -> coarse bucket used for routing."""
    if value >= 0.85:
        return ConfidenceLevel.HIGH
    if value >= 0.60:
        return ConfidenceLevel.MODERATE
    if value >= 0.30:
        return ConfidenceLevel.LOW
    return ConfidenceLevel.INSUFFICIENT


@dataclass
class VerificationStatePropagator:
    """Lifts safety-engine outcomes onto interop envelopes."""

    # Optional — when present, the propagator also threads per-claim
    # verification nodes into the shared context graph.
    context_protocol: SwarmContextProtocol | None = None

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def lift(
        self,
        envelope: AgentContextEnvelope,
        outcome: VerificationOutcome,
    ) -> AgentContextEnvelope:
        """Return a new envelope with the outcome's safety state applied."""
        tier = str(getattr(outcome, "tier", "") or "").lower()
        state = _TIER_TO_STATE.get(tier, VerificationState.PENDING)

        decision = getattr(outcome, "decision", None)
        confidence_value = 1.0
        if decision is not None:
            score = getattr(decision, "score", None)
            if score is not None:
                confidence_value = float(getattr(score, "confidence", 1.0) or 1.0)

        annotated = envelope.with_verification(
            state,
            confidence_level=_confidence_level_for(confidence_value),
            confidence_value=confidence_value,
        )

        if self.context_protocol is not None:
            self._propagate_to_graph(outcome)

        return annotated

    def lift_with_agent(
        self,
        envelope: AgentContextEnvelope,
        *,
        agent: BiomedicalVerificationAgent,
        run_dict: dict[str, Any],
    ) -> AgentContextEnvelope:
        """Run the safety agent inline and lift its outcome."""
        outcome = agent.verify_run(
            run_dict,
            correlation_id=envelope.workflow_id,
        )
        return self.lift(envelope, outcome)

    # ------------------------------------------------------------------
    # Pre-send guard adapter
    # ------------------------------------------------------------------

    def as_pre_send_guard(
        self,
        agent: BiomedicalVerificationAgent,
    ):
        """Return a callable that agents use to verify before sending.

        Usage::

            guard = propagator.as_pre_send_guard(agent=safety_agent)
            safe_env = guard(envelope, run_dict=run)
            bus.send(safe_env)

        The bus's safety_gate catches FAILED envelopes; this guard
        gives agents the option to check *before* they publish so
        they can escalate rather than hitting the gate.
        """

        def _guard(
            envelope: AgentContextEnvelope,
            *,
            run_dict: dict[str, Any],
        ) -> AgentContextEnvelope:
            return self.lift_with_agent(
                envelope,
                agent=agent,
                run_dict=run_dict,
            )

        return _guard

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _propagate_to_graph(self, outcome: VerificationOutcome) -> None:
        """Append per-claim VerificationNodes to the shared context graph."""
        if self.context_protocol is None:
            return
        traces = list(getattr(outcome, "traces", []) or [])
        if not traces:
            return
        from interoperability.shared_context.protocol import (
            ContextDelta,
            DeltaKind,
        )

        for tr in traces:
            claim_id = getattr(tr, "claim_id", "") or ""
            if not claim_id:
                continue
            check_name = getattr(tr, "rule_id", "") or getattr(tr, "validator", "")
            verdict = str(getattr(tr, "state", "") or "pass").lower()
            node = VerificationNode(
                check_id=f"{claim_id}:{check_name}",
                claim_id=claim_id,
                check_name=check_name,
                verdict=verdict,
                reason=str(getattr(tr, "reason", "") or ""),
                confidence=float(getattr(tr, "confidence", 1.0) or 1.0),
            )
            try:
                self.context_protocol.apply(
                    ContextDelta(
                        kind=DeltaKind.ADD_VERDICT,
                        payload=node,
                        agent_id=self.context_protocol.agent_id,
                        claim_id=claim_id,
                    )
                )
            except Exception:
                # A graph-update failure must not disrupt message flow.
                continue


__all__ = ["VerificationStatePropagator"]
