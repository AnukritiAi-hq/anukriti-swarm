"""Event emitter for observability and tracing.

Collects SwarmEvents and dispatches them to registered listeners.
Supports multiple listeners (console logger, file writer, future telemetry).
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Callable, Generator

from events.types import EventCategory, EventSeverity, SwarmEvent

logger = logging.getLogger("anukriti_swarm.events")

EventListener = Callable[[SwarmEvent], None]


class EventEmitter:
    """Central event emitter for the swarm.

    Agents emit events through this emitter. Listeners receive events
    for logging, tracing, alerting, or audit trail construction.

    Thread-safety: Current implementation is single-threaded.
    Future: Will use asyncio or thread-safe queues for concurrent access.
    """

    def __init__(self) -> None:
        self._listeners: list[EventListener] = []
        self._category_listeners: dict[EventCategory, list[EventListener]] = defaultdict(list)
        self._events: list[SwarmEvent] = []

    def add_listener(self, listener: EventListener, category: EventCategory | None = None) -> None:
        """Register a listener. If category is set, only receives that category."""
        if category:
            self._category_listeners[category].append(listener)
        else:
            self._listeners.append(listener)

    def emit(self, event: SwarmEvent) -> None:
        """Emit an event to all registered listeners."""
        self._events.append(event)
        for listener in self._listeners:
            listener(event)
        for listener in self._category_listeners.get(event.category, []):
            listener(event)

    @contextmanager
    def trace_execution(
        self, agent_id: str, correlation_id: str, action: str
    ) -> Generator[None, None, None]:
        """Context manager that emits start/end events with timing."""
        self.emit(SwarmEvent(
            category=EventCategory.EXECUTION,
            severity=EventSeverity.INFO,
            agent_id=agent_id,
            correlation_id=correlation_id,
            action=f"{action}_started",
        ))
        t0 = time.perf_counter()
        try:
            yield
        except Exception as exc:
            self.emit(SwarmEvent(
                category=EventCategory.EXECUTION,
                severity=EventSeverity.ERROR,
                agent_id=agent_id,
                correlation_id=correlation_id,
                action=f"{action}_failed",
                details={"error": str(exc)},
            ))
            raise
        else:
            duration_ms = (time.perf_counter() - t0) * 1000
            self.emit(SwarmEvent(
                category=EventCategory.EXECUTION,
                severity=EventSeverity.INFO,
                agent_id=agent_id,
                correlation_id=correlation_id,
                action=f"{action}_completed",
                duration_ms=round(duration_ms, 1),
            ))

    def get_events(self, correlation_id: str | None = None) -> list[SwarmEvent]:
        """Get collected events, optionally filtered."""
        if correlation_id:
            return [e for e in self._events if e.correlation_id == correlation_id]
        return list(self._events)

    def summary(self, correlation_id: str) -> str:
        """Human-readable summary of events for a correlation_id."""
        events = self.get_events(correlation_id)
        lines = [f"Events ({len(events)}) for {correlation_id}:"]
        for e in events:
            dur = f" [{e.duration_ms:.0f}ms]" if e.duration_ms else ""
            lines.append(f"  {e.severity.value:>5} | {e.agent_id:<25} | {e.action}{dur}")
        return "\n".join(lines)


def console_listener(event: SwarmEvent) -> None:
    """Default listener that logs events to console."""
    logger.info("[%s] %s | %s | %s", event.severity.value, event.agent_id, event.action, event.details or "")
