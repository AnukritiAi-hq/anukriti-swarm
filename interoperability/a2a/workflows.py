"""A2A workflow primitives for genomic-agent collaboration.

Closes requirement #9 of the interoperability brief. Five pure
functions over ``AgentMessageBus`` + ``SharedBiomedicalContext``
+ ``SwarmContextProtocol``:

    delegate_to_specialist    orchestrator → specialist dispatch
    collaborate               parallel multi-specialist invocation
    escalate_to_safety        verification-failure hand-off
    verify_handoff            per-claim verification exchange
    sync_evidence             bi-directional evidence propagation

All five are **genomic-scoped**: they refuse to delegate to agents
that aren't registered on the ``AgentMessageBus`` with a genomic
role, and every message they produce carries a
``biomedical_context_type`` header.

Non-goals
---------
- Not an abstract "agent protocol" framework. These 5 operations
  are the closed set of inter-agent primitives the brief names.
  Adding a sixth means adding another function here, not extending
  a generic registry.
- Not async. All five return synchronously. Async versions land
  as a sibling module if/when a demo needs parallel-in-time
  specialist execution (today the bus dispatches are cheap
  sub-millisecond deterministic work).
- Not a clinical workflow engine. These are specialist-to-specialist
  operations inside the genomic pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from interoperability.shared_context.envelope import (
    AgentContextEnvelope,
    BiomedicalContextType,
    VerificationState,
)

if TYPE_CHECKING:  # pragma: no cover
    from agents.verification.agent import (
        BiomedicalVerificationAgent,
        VerificationOutcome,
    )
    from interoperability.agent_bus.bus import AgentMessageBus
    from interoperability.mcp_protocol.provenance_layer import (
        ProvenancePropagationLayer,
    )
    from interoperability.mcp_protocol.verification_propagator import (
        VerificationStatePropagator,
    )
    from interoperability.shared_context.biomedical import (
        SharedBiomedicalContext,
    )


@dataclass
class DelegationResult:
    """Outcome of a single ``delegate_to_specialist`` call."""

    delegated_to: str
    envelope_sent: AgentContextEnvelope
    reply: AgentContextEnvelope | None
    delivered: bool

    @property
    def has_reply(self) -> bool:
        return self.reply is not None


@dataclass
class CollaborationResult:
    """Outcome of a ``collaborate`` fan-out."""

    delegations: list[DelegationResult] = field(default_factory=list)

    @property
    def successful(self) -> int:
        return sum(1 for d in self.delegations if d.delivered)

    @property
    def replies(self) -> list[AgentContextEnvelope]:
        return [d.reply for d in self.delegations if d.reply is not None]


# ---------------------------------------------------------------------------
# 1. delegate_to_specialist
# ---------------------------------------------------------------------------


def delegate_to_specialist(
    *,
    bus: "AgentMessageBus",
    from_agent: str,
    to_agent: str,
    context_type: BiomedicalContextType,
    workflow_id: str,
    payload: dict[str, Any] | None = None,
    evidence_references: tuple[str, ...] = (),
    provenance_layer: "ProvenancePropagationLayer | None" = None,
) -> DelegationResult:
    """Orchestrator-to-specialist dispatch through the bus.

    Builds an ``AgentContextEnvelope`` targeted at ``to_agent``,
    stamps provenance (when a ``provenance_layer`` is supplied),
    sends it via the bus, and returns the delivery outcome.

    The bus enforces:
      - genomic scope (envelope has a biomedical_context_type)
      - target-agent scope filter (if the specialist registered
        with ``context_types=`` that excludes ``context_type``,
        the delegation lands in the rejected queue)
    """
    envelope = AgentContextEnvelope(
        originating_agent=from_agent,
        workflow_id=workflow_id,
        target_agent=to_agent,
        biomedical_context_type=context_type,
        payload=payload or {},
        evidence_references=evidence_references,
    )
    if provenance_layer is not None:
        envelope = provenance_layer.stamp(envelope)
    reply = bus.send(envelope)
    delivered = envelope not in bus.rejected
    return DelegationResult(
        delegated_to=to_agent,
        envelope_sent=envelope,
        reply=reply,
        delivered=delivered,
    )


# ---------------------------------------------------------------------------
# 2. collaborate
# ---------------------------------------------------------------------------


def collaborate(
    *,
    bus: "AgentMessageBus",
    from_agent: str,
    specialists: list[tuple[str, BiomedicalContextType]],
    workflow_id: str,
    payload: dict[str, Any] | None = None,
    evidence_references: tuple[str, ...] = (),
    provenance_layer: "ProvenancePropagationLayer | None" = None,
) -> CollaborationResult:
    """Parallel (sequential-in-time) multi-specialist invocation.

    For each ``(agent_id, context_type)`` pair, runs
    ``delegate_to_specialist``. Replies are collected into a single
    ``CollaborationResult``. Specialists are NOT guaranteed to see
    each other's replies during the collaboration — that's what
    ``sync_evidence`` is for.
    """
    result = CollaborationResult()
    for agent_id, ctx_type in specialists:
        result.delegations.append(
            delegate_to_specialist(
                bus=bus,
                from_agent=from_agent,
                to_agent=agent_id,
                context_type=ctx_type,
                workflow_id=workflow_id,
                payload=payload,
                evidence_references=evidence_references,
                provenance_layer=provenance_layer,
            )
        )
    return result


# ---------------------------------------------------------------------------
# 3. escalate_to_safety
# ---------------------------------------------------------------------------


def escalate_to_safety(
    *,
    bus: "AgentMessageBus",
    from_agent: str,
    workflow_id: str,
    run_dict: dict[str, Any],
    agent: "BiomedicalVerificationAgent",
    propagator: "VerificationStatePropagator",
    target_agent: str = "safety_agent",
) -> AgentContextEnvelope:
    """Hand off a suspect claim to the safety agent.

    Builds a ``VERIFICATION``-kind envelope, runs the safety agent
    via the propagator (``lift_with_agent``) to get a
    ``VerificationOutcome``, and returns the lifted envelope. The
    bus's ``safety_gate`` refuses to route ``FAILED`` envelopes —
    callers use ``envelope.is_safe`` to decide whether to proceed.

    Does NOT call ``bus.send()`` — escalation produces a signed
    envelope that the caller chooses what to do with (continue the
    workflow, surface a block, request evidence). This keeps the
    safety handoff separable from delivery semantics.
    """
    envelope = AgentContextEnvelope(
        originating_agent=from_agent,
        target_agent=target_agent,
        workflow_id=workflow_id,
        biomedical_context_type=BiomedicalContextType.VERIFICATION,
        payload={"escalation_reason": "safety_handoff", "run": run_dict},
    )
    return propagator.lift_with_agent(
        envelope, agent=agent, run_dict=run_dict,
    )


# ---------------------------------------------------------------------------
# 4. verify_handoff
# ---------------------------------------------------------------------------


def verify_handoff(
    *,
    bus: "AgentMessageBus",
    envelope: AgentContextEnvelope,
    outcome: "VerificationOutcome",
    propagator: "VerificationStatePropagator",
) -> AgentContextEnvelope:
    """Lift a completed verification onto the envelope and re-send.

    Used when one specialist produces a claim and another (typically
    a verification or narrative agent) finishes the safety check.
    The caller holds the already-produced ``VerificationOutcome``,
    and ``verify_handoff`` applies it to the envelope + publishes
    the result so downstream subscribers see the updated state.

    If the lifted envelope becomes ``FAILED``, the bus's safety gate
    blocks delivery — the caller inspects ``returned.is_safe`` to
    know whether the handoff passed.
    """
    lifted = propagator.lift(envelope, outcome)
    bus.send(lifted)
    return lifted


# ---------------------------------------------------------------------------
# 5. sync_evidence
# ---------------------------------------------------------------------------


def sync_evidence(
    *,
    bus: "AgentMessageBus",
    from_agent: str,
    workflow_id: str,
    evidence_references: tuple[str, ...],
    target_agents: list[str] | None = None,
    provenance_layer: "ProvenancePropagationLayer | None" = None,
) -> list[AgentContextEnvelope]:
    """Push an evidence bundle to every specialist that needs it.

    When ``target_agents`` is supplied, the function sends one
    ``EVIDENCE``-kind envelope per target agent. When it's None,
    the function broadcasts (no target_agent) so every subscriber
    of ``BiomedicalContextType.EVIDENCE`` receives the bundle.

    Returns the list of sent envelopes so the caller can inspect
    which made it through the bus's safety + scope gates.
    """
    sent: list[AgentContextEnvelope] = []
    if target_agents:
        for target in target_agents:
            env = AgentContextEnvelope(
                originating_agent=from_agent,
                workflow_id=workflow_id,
                target_agent=target,
                biomedical_context_type=BiomedicalContextType.EVIDENCE,
                evidence_references=evidence_references,
                verification_state=VerificationState.PASSED,
            )
            if provenance_layer is not None:
                env = provenance_layer.stamp(env)
            bus.send(env)
            sent.append(env)
    else:
        env = AgentContextEnvelope(
            originating_agent=from_agent,
            workflow_id=workflow_id,
            biomedical_context_type=BiomedicalContextType.EVIDENCE,
            evidence_references=evidence_references,
            verification_state=VerificationState.PASSED,
        )
        if provenance_layer is not None:
            env = provenance_layer.stamp(env)
        bus.send(env)
        sent.append(env)
    return sent


__all__ = [
    "DelegationResult",
    "CollaborationResult",
    "delegate_to_specialist",
    "collaborate",
    "escalate_to_safety",
    "verify_handoff",
    "sync_evidence",
]
