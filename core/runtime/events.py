"""``RuntimeEvent`` + ``EventStream`` — runtime event surface.

Phase 2, commit 4 of the Unified Orchestration + Visualization brief.

Defines the shape of events the ``SwarmRuntime`` (commit 5) emits
at every lifecycle boundary and the abstract sink interface any
consumer implements. The FastAPI WebSocket endpoint (phase 3) will
implement a concrete sink that forwards events to connected clients.

Closed event kinds
------------------

Event kinds are a **closed enum** — extending is a code change.
Chosen to match the existing ``observability.ExecutionTracer.EventKind``
vocabulary where concepts align, plus 5 sufficiency-specific kinds
that the existing tracer can't represent cleanly:

    RUN_STARTED              new lifecycle begins; carries scope
    AGENT_ACTIVATED          a specialist agent fires
    RETRIEVAL_COMPLETE       retrieval stage produced an evidence set
    GRAPH_TRAVERSAL          KG reasoning produced paths
    SUFFICIENCY_DECISION     sufficiency engine emitted a decision
    VERIFICATION_CHECKPOINT  set-level verifier emitted a verdict
    UNCERTAINTY_TRANSITION   uncertainty tier / action recorded
    PROVENANCE_PERSISTED     provenance chain persisted (or would be)
    SYNTHESIS_EMITTED        narrative synthesis produced
    SAFE_ABSTENTION          runtime refused to synthesize; terminal
    RUN_COMPLETED            lifecycle ended (success)
    RUN_FAILED               lifecycle ended (fatal error)

Scope firewall
--------------
Event kinds are the only allowed channel names. A sink cannot be
passed an unknown event kind — the enum enforces.

Every event carries:
    event_id        16-char hex id (uuid slice)
    kind            closed RuntimeEventKind
    correlation_id  MCP linkage to the run
    timestamp       ISO timestamp (UTC)
    payload         primitive-only dict (JSON-safe)

Usage
-----
Sink implementations receive events via ``stream.emit(event)``. The
default ``InMemoryEventStream`` appends to a list a caller can later
replay. The FastAPI WebSocket sink (phase 3) will push events into
a client's connection as they arrive.
"""

from __future__ import annotations

import abc
import contextlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


class RuntimeEventKind(str, Enum):
    """Closed event kinds emitted by SwarmRuntime. Extending is a code change."""

    RUN_STARTED = "run_started"
    AGENT_ACTIVATED = "agent_activated"
    RETRIEVAL_COMPLETE = "retrieval_complete"
    GRAPH_TRAVERSAL = "graph_traversal"
    SUFFICIENCY_DECISION = "sufficiency_decision"
    VERIFICATION_CHECKPOINT = "verification_checkpoint"
    UNCERTAINTY_TRANSITION = "uncertainty_transition"
    PROVENANCE_PERSISTED = "provenance_persisted"
    SYNTHESIS_EMITTED = "synthesis_emitted"
    SAFE_ABSTENTION = "safe_abstention"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"


@dataclass(frozen=True)
class RuntimeEvent:
    """Frozen per-event record. Hashable by event_id.

    Fields
    ------
    event_id        16-char hex id (uuid slice), uniquely identifies
                    this emission
    kind            closed RuntimeEventKind
    correlation_id  MCP + context linkage
    timestamp       ISO timestamp; set by the runtime at emit time
    payload         primitive-only dict, JSON-safe; the one free-form
                    field but constrained by convention to hold only
                    strings / numbers / booleans / lists / dicts of
                    the same
    """

    kind: RuntimeEventKind
    correlation_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind.value,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": dict(self.payload),
        }


# ---------------------------------------------------------------------------
# Sink ABC
# ---------------------------------------------------------------------------


class EventStream(abc.ABC):
    """Abstract sink for RuntimeEvent.

    Implementations MUST be callable-safe from the SwarmRuntime's
    execution thread. The FastAPI WebSocket sink (phase 3) will wrap
    an asyncio.Queue; the InMemoryEventStream (below) is synchronous.
    """

    @abc.abstractmethod
    def emit(self, event: RuntimeEvent) -> None:  # pragma: no cover
        """Record ``event``. Must not raise — broken sinks break runs."""

    def close(self) -> None:
        """Optional: signal end-of-run. Default is a no-op."""

        return None


# ---------------------------------------------------------------------------
# InMemoryEventStream — default sink for demos/tests
# ---------------------------------------------------------------------------


@dataclass
class InMemoryEventStream(EventStream):
    """Synchronous in-memory sink; appends every event to a list.

    Used by the unified demo and by tests. Safe to hand to one
    SwarmRuntime per instance; NOT thread-safe by design (the FastAPI
    sink in phase 3 uses asyncio.Queue for its concurrency).
    """

    events: list[RuntimeEvent] = field(default_factory=list)
    subscribers: list[Callable[[RuntimeEvent], None]] = field(default_factory=list)
    _closed: bool = False

    def emit(self, event: RuntimeEvent) -> None:
        if self._closed:
            # Silent drop after close — callers who re-emit after
            # close() are buggy, but the runtime must not raise here.
            return
        self.events.append(event)
        for subscriber in list(self.subscribers):
            # Broken subscribers cannot break the runtime — silently
            # drop any exception they raise. pragma: no cover — defensive.
            with contextlib.suppress(Exception):
                subscriber(event)

    def close(self) -> None:
        self._closed = True

    # Convenience helpers -------------------------------------------------

    def subscribe(self, handler: Callable[[RuntimeEvent], None]) -> None:
        """Register a synchronous handler invoked on every future emit.

        Handlers MUST NOT raise; exceptions are swallowed by emit.
        """

        self.subscribers.append(handler)

    def __iter__(self) -> Iterator[RuntimeEvent]:
        return iter(self.events)

    def by_kind(self, kind: RuntimeEventKind) -> list[RuntimeEvent]:
        """Return all events of a given kind in emission order."""

        return [e for e in self.events if e.kind is kind]

    def to_list(self) -> list[dict[str, Any]]:
        """Full event stream as JSON-safe dicts."""

        return [e.to_dict() for e in self.events]


__all__ = [
    "RuntimeEventKind",
    "RuntimeEvent",
    "EventStream",
    "InMemoryEventStream",
]
