"""Typed message envelopes and protocol definitions.

Every inter-agent communication is wrapped in a MessageEnvelope that carries:
- Routing: source, target, message type
- Tracing: correlation_id, causation_id, trace_id
- Provenance: timestamp, origin (deterministic/generative)
- Metadata: priority, TTL, retry count

Design: Immutable (frozen) Pydantic models ensure messages are never
modified after creation — they are append-only in the audit trail.

Compatibility:
- MCP: envelope metadata maps to MCP tool call context
- Distributed: serializable via model_dump_json() for network transport
- A2A: supports request/response correlation via reply_to field
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Classification of inter-agent messages."""

    # Task lifecycle
    TASK_DELEGATE = "task_delegate"
    TASK_RESULT = "task_result"
    TASK_ERROR = "task_error"

    # Evidence flow
    EVIDENCE_REQUEST = "evidence_request"
    EVIDENCE_RESPONSE = "evidence_response"

    # Verification
    VERIFY_REQUEST = "verify_request"
    VERIFY_RESPONSE = "verify_response"

    # Escalation
    ESCALATION = "escalation"
    ESCALATION_RESOLVED = "escalation_resolved"

    # Orchestration
    ORCHESTRATION_UPDATE = "orchestration_update"
    STAGE_COMPLETE = "stage_complete"

    # Signals
    SIGNAL_ABORT = "signal_abort"
    SIGNAL_CHECKPOINT = "signal_checkpoint"
    HEARTBEAT = "heartbeat"


class Priority(int, Enum):
    """Message priority levels."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 5
    LOW = 8
    BACKGROUND = 9


class DeliveryStatus(str, Enum):
    """Message delivery tracking status."""

    PENDING = "pending"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    EXPIRED = "expired"


class MessageEnvelope(BaseModel):
    """Immutable message envelope for inter-agent communication.

    Every message in the swarm is wrapped in this envelope. It provides
    full traceability through correlation/causation IDs and supports
    request/response patterns via reply_to.

    Tracing fields:
    - correlation_id: links all messages in the same execution run
    - causation_id: the message_id that caused this message to be sent
    - trace_id: groups messages for distributed tracing (OpenTelemetry-compatible)
    """

    # Identity
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)

    # Routing
    source_agent: str = Field(..., description="Sending agent ID")
    target_agent: str | None = Field(None, description="Target agent (None = broadcast)")
    message_type: MessageType
    reply_to: str | None = Field(None, description="Message ID this is responding to")

    # Payload
    payload: dict[str, Any] = Field(default_factory=dict)

    # Tracing
    correlation_id: str = Field(..., description="Execution run identifier")
    causation_id: str | None = Field(None, description="Message that caused this one")
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])

    # Metadata
    priority: Priority = Priority.NORMAL
    ttl_seconds: int | None = Field(None, description="Time-to-live (None = no expiry)")
    retry_count: int = Field(0, ge=0)
    max_retries: int = Field(2, ge=0)

    # Provenance
    origin: str = Field("deterministic", description="deterministic or generative")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Delivery
    status: DeliveryStatus = DeliveryStatus.PENDING

    model_config = {"frozen": True}

    def create_reply(
        self,
        source_agent: str,
        message_type: MessageType,
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> "MessageEnvelope":
        """Create a reply message linked to this envelope."""
        return MessageEnvelope(
            source_agent=source_agent,
            target_agent=self.source_agent,
            message_type=message_type,
            payload=payload,
            reply_to=self.message_id,
            correlation_id=self.correlation_id,
            causation_id=self.message_id,
            trace_id=self.trace_id,
            **kwargs,
        )


# --- Typed payload helpers ---


def task_delegate_payload(
    task_id: str, agent_type: str, parameters: dict[str, Any], timeout: int = 30
) -> dict[str, Any]:
    """Construct a TASK_DELEGATE payload."""
    return {"task_id": task_id, "agent_type": agent_type, "parameters": parameters, "timeout": timeout}


def evidence_request_payload(gene: str, query: str, top_k: int = 5) -> dict[str, Any]:
    """Construct an EVIDENCE_REQUEST payload."""
    return {"gene": gene, "query": query, "top_k": top_k}


def escalation_payload(
    reason: str, severity: str, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Construct an ESCALATION payload."""
    return {"reason": reason, "severity": severity, "context": context or {}}
