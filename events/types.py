"""Typed event definitions for execution tracing and observability.

Events are emitted at key points in the pipeline and consumed by
logging, tracing, and monitoring systems. They are distinct from
messages (events are observational; messages are operational).

Compatibility:
- OpenTelemetry: events map to span events with attributes
- Structured logging: events serialize to JSON log lines
- Future: event streaming to external systems (Kafka, CloudWatch)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventCategory(str, Enum):
    """High-level event classification."""

    LIFECYCLE = "lifecycle"       # Agent start/stop/error
    COMMUNICATION = "communication"  # Message sent/received
    EXECUTION = "execution"      # Task execution progress
    VERIFICATION = "verification"  # Verification checks
    ESCALATION = "escalation"    # Escalation triggers
    MEMORY = "memory"            # Memory read/write operations


class EventSeverity(str, Enum):
    """Event severity for filtering and alerting."""

    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


class SwarmEvent(BaseModel):
    """A single observable event in the swarm execution.

    Events provide full observability into the pipeline without
    affecting execution flow. They are fire-and-forget — emitting
    an event never blocks or fails the pipeline.
    """

    event_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex[:12])
    category: EventCategory
    severity: EventSeverity = EventSeverity.INFO
    agent_id: str
    correlation_id: str
    action: str = Field(..., description="e.g., 'task_started', 'message_sent', 'check_passed'")
    details: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}
