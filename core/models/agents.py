"""Agent communication, verification, escalation, and audit models.

Defines the typed structures for inter-agent messaging, verification
outcomes, escalation events, and immutable audit trail entries.

These models enforce the safety architecture:
- Every agent output is verified before reaching the user
- Escalation events trigger human review for uncertain cases
- Audit entries provide full reproducibility and traceability
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from core.models.genomics import OriginType


class AgentRole(str, Enum):
    """Agent role classification in the swarm."""

    ORCHESTRATOR = "orchestrator"
    POPULATION = "population"
    CHROMOSOME = "chromosome"
    PHARMACOGENE = "pharmacogene"
    RETRIEVAL = "retrieval"
    VERIFICATION = "verification"
    NARRATIVE = "narrative"


class MessageType(str, Enum):
    """Types of inter-agent messages."""

    TASK_ASSIGN = "task_assign"
    TASK_RESULT = "task_result"
    TASK_ERROR = "task_error"
    EVIDENCE_REQUEST = "evidence_request"
    EVIDENCE_RESPONSE = "evidence_response"
    VERIFY_REQUEST = "verify_request"
    VERIFY_RESULT = "verify_result"
    ESCALATE = "escalate"
    SIGNAL_ABORT = "signal_abort"


class VerificationVerdict(str, Enum):
    """Outcome of a verification check."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


class EscalationSeverity(str, Enum):
    """Severity of an escalation event."""

    LOW = "low"          # Informational, no action needed
    MEDIUM = "medium"    # Review recommended
    HIGH = "high"        # Blocks pipeline, human review required
    CRITICAL = "critical"  # Safety concern, immediate attention


class AgentMessage(BaseModel):
    """Immutable message exchanged between agents via the memory layer.

    All inter-agent communication uses this structure. Messages are
    append-only in the audit trail — never modified after creation.

    Future: Will support message priority queuing, TTL expiration,
    and dead-letter routing for undeliverable messages.
    """

    message_id: str = Field(..., description="Unique message identifier (UUID)")
    source_agent: str = Field(..., description="Sending agent ID")
    target_agent: str | None = Field(None, description="Receiving agent ID (None = broadcast)")
    message_type: MessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = Field(..., description="Links messages in same execution chain")
    priority: int = Field(5, ge=0, le=9, description="0 = highest, 9 = lowest")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class VerificationResult(BaseModel):
    """Outcome of a verification check on an agent's output.

    Each check validates one aspect of the output (source attribution,
    confidence threshold, evidence support, contradiction scan, scope).

    Future: Will support weighted check scoring and configurable
    thresholds per deployment context.
    """

    check_name: str = Field(..., description="e.g., 'source_attribution', 'confidence_threshold'")
    verdict: VerificationVerdict
    details: str = Field("", description="Human-readable explanation")
    expected: str | None = None
    actual: str | None = None
    agent_id: str = Field(..., description="Agent whose output was verified")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VerificationReport(BaseModel):
    """Aggregated verification results for a single agent output.

    The overall verdict is PASS only if all individual checks pass.
    Any FAIL check blocks the output from reaching the narrative agent.
    """

    target_agent: str
    gene: str | None = None
    checks: list[VerificationResult] = Field(default_factory=list)
    overall_verdict: VerificationVerdict = VerificationVerdict.PASS
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def compute_verdict(self) -> VerificationVerdict:
        """Compute overall verdict from individual checks."""
        if any(c.verdict == VerificationVerdict.FAIL for c in self.checks):
            return VerificationVerdict.FAIL
        if any(c.verdict == VerificationVerdict.WARN for c in self.checks):
            return VerificationVerdict.WARN
        return VerificationVerdict.PASS


class EscalationEvent(BaseModel):
    """An event requiring human review or intervention.

    Triggered when verification fails, contradictions are detected,
    or confidence falls below acceptable thresholds.

    Future: Will integrate with alerting systems and support
    escalation routing to domain-specific reviewers.
    """

    event_id: str
    severity: EscalationSeverity
    source_agent: str
    reason: str = Field(..., description="Why escalation was triggered")
    context: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str
    resolved: bool = False
    resolution: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditEntry(BaseModel):
    """Immutable audit trail entry for a single agent action.

    Every agent execution, memory access, and verification decision
    is recorded as an audit entry. These are append-only and retained
    indefinitely for full reproducibility.

    Future: Will support cryptographic integrity (hash chaining),
    compliance export formats, and temporal queries.
    """

    entry_id: str
    correlation_id: str
    agent_id: str
    agent_role: AgentRole
    action: str = Field(..., description="e.g., 'execute', 'memory_read', 'verify'")
    inputs_hash: str | None = Field(None, description="SHA-256 of input data")
    outputs_hash: str | None = Field(None, description="SHA-256 of output data")
    duration_ms: float | None = None
    origin: OriginType = OriginType.DETERMINISTIC
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}
