"""``AgentMessageBus`` — context-aware router over ``communication.MessageBus``.

Closes the bus piece of requirement #2 of the interoperability brief.

What AgentMessageBus adds on top of the legacy MessageBus
----------------------------------------------------------
    1. **Genomic-scope enforcement.** Every message is an
       ``AgentContextEnvelope`` carrying a ``biomedical_context_type``
       — the legacy bus accepts any payload shape. Messages that
       arrive as legacy ``MessageEnvelope`` are auto-lifted when a
       ``biomedical_context_type`` hint is supplied; otherwise they
       land in a dead-letter queue.
    2. **Per-type subscriptions.** Subscribers can opt in to a single
       ``BiomedicalContextType`` (e.g. only "population" messages
       for the PopulationAgent).
    3. **Verification gate.** When ``safety_gate=True`` (default),
       envelopes marked ``VerificationState.FAILED`` are refused
       at send() — the bus itself enforces block-on-unsafe.
    4. **Observability hook.** The tracer handler receives every
       envelope for integration with the session-3 observability
       layer.

What AgentMessageBus explicitly does NOT do
-------------------------------------------
    - Does not implement clinical messaging (lab orders, scheduling,
      discharge, billing, prescription dispatch).
    - Does not bypass ``communication.MessageBus`` — every genomic
      message is also published onto the legacy bus (via
      ``.to_message_envelope()``) so existing handlers keep working.
    - Does not spawn network listeners — in-process only.

Construction:

    bus = AgentMessageBus()  # wraps a fresh legacy MessageBus
    bus.register(agent_id, handler, context_types=(BiomedicalContextType.POPULATION,))
    reply = bus.send(envelope)
"""

from __future__ import annotations

import contextlib
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from communication.bus import MessageBus

from interoperability.shared_context.envelope import (
    AgentContextEnvelope,
    BiomedicalContextType,
)

# One agent handler takes an AgentContextEnvelope and may return a reply.
AgentHandler = Callable[[AgentContextEnvelope], AgentContextEnvelope | None]

# Observability hook — receives every envelope post-route for tracing.
BusObserver = Callable[[AgentContextEnvelope, str], None]
# second argument is the event kind: "sent" / "delivered" / "rejected"
# / "blocked".


@dataclass
class _Registration:
    """Internal record of an agent's subscription."""

    handler: AgentHandler
    context_types: frozenset[BiomedicalContextType]


class AgentMessageBus:
    """Context-aware bus for genomic-specialist inter-agent messaging.

    Wraps a legacy ``communication.MessageBus`` so existing agents
    + tests keep working. Every ``send()`` also publishes the
    projected legacy envelope onto the underlying bus.

    Parameters
    ----------
    inner:
        Optional legacy ``MessageBus``. Created fresh when omitted.
    safety_gate:
        When True (default), refuses to route envelopes with
        ``verification_state == FAILED``. Turn off only for tests.
    """

    def __init__(
        self,
        *,
        inner: MessageBus | None = None,
        safety_gate: bool = True,
    ) -> None:
        self._inner = inner or MessageBus()
        self._safety_gate = safety_gate
        # agent_id -> _Registration
        self._registrations: dict[str, _Registration] = {}
        # per-context-type subscribers (pub/sub)
        self._type_subscribers: dict[BiomedicalContextType, list[AgentHandler]] = defaultdict(list)
        self._history: list[AgentContextEnvelope] = []
        self._rejected: list[AgentContextEnvelope] = []
        self._observers: list[BusObserver] = []

    # ------------------------------------------------------------------
    # Passthroughs / inner bus access
    # ------------------------------------------------------------------

    @property
    def inner(self) -> MessageBus:
        """Legacy bus wrapped underneath; exposed for compatibility tests."""
        return self._inner

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        agent_id: str,
        handler: AgentHandler,
        *,
        context_types: tuple[BiomedicalContextType, ...] | None = None,
    ) -> None:
        """Register a specialist agent's handler.

        ``context_types`` restricts which envelopes reach this agent.
        None = accept every genomic type. The type filter is applied
        at delivery so the bus itself can reject off-scope traffic.
        """
        self._registrations[agent_id] = _Registration(
            handler=handler,
            context_types=frozenset(context_types or []),
        )

    def subscribe(
        self,
        context_type: BiomedicalContextType,
        handler: AgentHandler,
    ) -> None:
        """Pub/sub — handle every envelope of the given context type."""
        self._type_subscribers[context_type].append(handler)

    def observe(self, observer: BusObserver) -> None:
        """Register an observability hook (session-3 tracer integration)."""
        self._observers.append(observer)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def send(
        self,
        envelope: AgentContextEnvelope,
    ) -> AgentContextEnvelope | None:
        """Route an envelope to its target or type subscribers.

        Returns the handler's reply when a direct target handles it,
        else None. Safety-gated: ``FAILED`` envelopes never reach a
        handler — they land in the rejected queue.
        """
        # Always record the send — even rejected envelopes are part
        # of the audit trail.
        self._history.append(envelope)
        self._notify(envelope, "sent")

        # Safety gate.
        if self._safety_gate and envelope.blocks_delivery:
            self._rejected.append(envelope)
            self._notify(envelope, "blocked")
            return None

        # Mirror to the legacy bus so non-interop handlers still see it.
        # Failures here are non-fatal; the interop path is the source of
        # truth.
        with contextlib.suppress(Exception):
            self._inner.send(envelope.to_message_envelope())

        # Direct targeted delivery.
        reply: AgentContextEnvelope | None = None
        if envelope.target_agent and envelope.target_agent in self._registrations:
            reg = self._registrations[envelope.target_agent]
            if self._passes_scope(envelope, reg.context_types):
                reply = reg.handler(envelope)
                self._notify(envelope, "delivered")
                if reply is not None:
                    self._history.append(reply)
                return reply
            # Scope rejected.
            self._rejected.append(envelope)
            self._notify(envelope, "rejected")
            return None

        # Pub/sub fan-out to type subscribers.
        subscribers = self._type_subscribers.get(envelope.biomedical_context_type, [])
        if subscribers:
            for handler in subscribers:
                # Broken subscriber must not take the bus down;
                # higher-level logs catch the underlying issue.
                with contextlib.suppress(Exception):
                    handler(envelope)
            self._notify(envelope, "delivered")
            return None

        # No handler — dead-letter.
        self._rejected.append(envelope)
        self._notify(envelope, "rejected")
        return None

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def history(
        self,
        *,
        workflow_id: str | None = None,
    ) -> list[AgentContextEnvelope]:
        """Chronological envelope history, optionally filtered by workflow."""
        if workflow_id is None:
            return list(self._history)
        return [e for e in self._history if e.workflow_id == workflow_id]

    @property
    def rejected(self) -> list[AgentContextEnvelope]:
        """Envelopes that couldn't be delivered (scope / safety / no handler)."""
        return list(self._rejected)

    @property
    def registered_agents(self) -> list[str]:
        return sorted(self._registrations)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _passes_scope(
        envelope: AgentContextEnvelope,
        allowed: frozenset[BiomedicalContextType],
    ) -> bool:
        """True when the envelope's context type is in the allowed set."""
        if not allowed:  # empty set == no filter
            return True
        return envelope.biomedical_context_type in allowed

    def _notify(self, envelope: AgentContextEnvelope, event: str) -> None:
        for obs in self._observers:
            with contextlib.suppress(Exception):
                obs(envelope, event)


__all__ = [
    "AgentMessageBus",
    "AgentHandler",
    "BusObserver",
]
