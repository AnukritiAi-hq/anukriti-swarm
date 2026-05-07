"""Anukriti Swarm — Logging and observability.

Provides structured logging for agent execution traces, enabling
full pipeline observability and audit trail generation.

Future: Will integrate with OpenTelemetry for distributed tracing
and emit structured events to the audit memory layer.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generator

# Configure structured logger
logger = logging.getLogger("anukriti_swarm")


@dataclass
class TraceEvent:
    """A single event in an execution trace."""

    agent_id: str
    event_type: str  # "start", "end", "error", "checkpoint"
    stage: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionTrace:
    """Complete execution trace for a pipeline run."""

    correlation_id: str
    events: list[TraceEvent] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add(self, agent_id: str, event_type: str, stage: str, **metadata: Any) -> None:
        event = TraceEvent(
            agent_id=agent_id, event_type=event_type, stage=stage, metadata=metadata
        )
        self.events.append(event)
        logger.info("[%s] %s | %s | %s", event_type.upper(), agent_id, stage, metadata or "")

    def summary(self) -> str:
        lines = [f"Trace: {self.correlation_id} ({len(self.events)} events)"]
        for e in self.events:
            dur = f" ({e.duration_ms:.0f}ms)" if e.duration_ms else ""
            lines.append(f"  [{e.event_type:>5}] {e.agent_id:<30} {e.stage}{dur}")
        return "\n".join(lines)


@contextmanager
def trace_agent(trace: ExecutionTrace, agent_id: str, stage: str) -> Generator[None, None, None]:
    """Context manager that records start/end timing for an agent execution."""
    trace.add(agent_id, "start", stage)
    t0 = time.perf_counter()
    try:
        yield
    except Exception as exc:
        trace.add(agent_id, "error", stage, error=str(exc))
        raise
    finally:
        duration_ms = (time.perf_counter() - t0) * 1000
        trace.add(agent_id, "end", stage, duration_ms=round(duration_ms, 1))


def setup_logging(level: int = logging.INFO) -> None:
    """Configure console logging for the swarm."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )
