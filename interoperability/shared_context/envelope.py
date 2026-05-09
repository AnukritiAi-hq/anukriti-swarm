"""``AgentContextEnvelope`` — interoperability-layer message envelope.

Closes requirement #4 of the interoperability brief. Every message
exchanged between specialist genomic agents via ``AgentMessageBus``
is wrapped in this envelope. It carries all 7 brief-required fields:

    originating_agent         source_agent (inherited from MessageEnvelope)
    workflow_id               correlation_id (aliased for clarity)
    evidence_references       list[str] of MCP evidence source_ids
    timestamp                 inherited
    verification_state        one of {pending, passed, warning, failed}
    confidence_level          one of {high, moderate, low, insufficient}
    biomedical_context_type   one of 7 genomic-scope kinds
                              (see BiomedicalContextType enum)

Why a new envelope, not just an extended MessageEnvelope?
----------------------------------------------------------
- Strict genomic scope: the ``biomedical_context_type`` is a
  closed enum with only genomic kinds. Unknown kinds are
  rejected at construction. Messages shaped for hospital /
  EHR / clinical-copilot workflows can't accidentally flow
  through the genomic bus.
- Safety-gate seam: ``verification_state`` is a first-class
  field, not buried in the payload. ``VerificationStatePropagator``
  (commit 7) reads this directly to decide whether to deliver.
- MCP compatibility: ``evidence_references`` is a top-level
  list so ``ProvenancePropagationLayer`` (commit 6) can
  stamp / read without unpacking the payload.

Design: Immutable (frozen) — once built, the envelope is the audit
record. If a downstream layer needs to annotate (e.g. append an
evidence reference after a retrieval hit), it builds a new envelope
via ``.with_evidence(...)`` / ``.with_verification(...)`` helpers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from communication.messages import (
    DeliveryStatus,
    MessageEnvelope,
    MessageType,
    Priority,
)


# ---------------------------------------------------------------------------
# Domain enums — strictly genomic scope
# ---------------------------------------------------------------------------


class BiomedicalContextType(str, Enum):
    """Closed enum — only genomic workflows.

    The brief explicitly excludes hospital / EHR / clinical-copilot
    workflows. Keeping this a closed enum (not a free-form string)
    makes the scope firewall enforceable at message-build time:
    a caller that tries to construct an envelope with a non-genomic
    type gets a pydantic validation error.

    Seven kinds, one per brief-named biomedical concept in req #3:
        population             population frequency / prevalence
        genotype               diplotype / allele call
        pharmacogene           phenotype inference + risk
        evidence               PMID / CPIC / guideline citations
        verification           safety-engine outcomes
        confidence             numeric reliability signal
        provenance             MCP provenance chain references
    """

    POPULATION = "population"
    GENOTYPE = "genotype"
    PHARMACOGENE = "pharmacogene"
    EVIDENCE = "evidence"
    VERIFICATION = "verification"
    CONFIDENCE = "confidence"
    PROVENANCE = "provenance"


class VerificationState(str, Enum):
    """Mirror of the safety-engine verification state for message-level use.

    Intentionally duplicated here so the interoperability layer
    doesn't couple to ``core.verification.trace.VerificationTrace``
    at import time (lazy-loading pattern used by the MCP layer).
    The values are wire-compatible with ``VerificationTrace.state``
    values ('pass' / 'warn' / 'fail') plus 'pending' for in-flight.
    """

    PENDING = "pending"
    PASSED = "pass"
    WARNING = "warn"
    FAILED = "fail"


class ConfidenceLevel(str, Enum):
    """Coarse-grained confidence bucket for routing decisions."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INSUFFICIENT = "insufficient"


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------


class AgentContextEnvelope(BaseModel):
    """Immutable genomic-scope envelope for inter-specialist messaging.

    Frozen pydantic model with all 7 brief-required fields explicit.
    Use ``.with_evidence(...)`` / ``.with_verification(...)`` to
    produce annotated copies.
    """

    # --- Identity (from underlying MessageEnvelope) ---
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)

    # --- 7 brief-required fields (req #4) ---
    originating_agent: str = Field(..., description="Sending agent ID")
    workflow_id: str = Field(..., description="correlation_id of the run")
    evidence_references: tuple[str, ...] = Field(
        default=(),
        description="MCP source IDs (PMIDs, CPIC guideline ids)",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    verification_state: VerificationState = VerificationState.PENDING
    confidence_level: ConfidenceLevel = ConfidenceLevel.MODERATE
    biomedical_context_type: BiomedicalContextType

    # --- Routing (matches MessageEnvelope) ---
    target_agent: str | None = Field(
        None, description="Target agent id (None = broadcast to subscribers)"
    )
    message_type: MessageType = MessageType.TASK_DELEGATE
    reply_to: str | None = None

    # --- Payload ---
    payload: dict[str, Any] = Field(default_factory=dict)

    # --- Tracing ---
    causation_id: str | None = None
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])

    # --- Metadata ---
    priority: Priority = Priority.NORMAL
    origin: str = Field("deterministic", description="'deterministic' or 'generative'")
    status: DeliveryStatus = DeliveryStatus.PENDING

    # --- Scalar confidence for propagation math (optional) ---
    confidence_value: float = Field(
        1.0, ge=0.0, le=1.0,
        description="Numeric confidence if available (0.0-1.0)",
    )

    model_config = {"frozen": True}

    # ------------------------------------------------------------------
    # Ergonomic accessors
    # ------------------------------------------------------------------

    @property
    def correlation_id(self) -> str:
        """Alias so callers that speak MessageEnvelope idioms work."""
        return self.workflow_id

    @property
    def source_agent(self) -> str:
        """Alias so callers that speak MessageEnvelope idioms work."""
        return self.originating_agent

    @property
    def is_safe(self) -> bool:
        """Convenience — VerificationStatePropagator uses this as the gate."""
        return self.verification_state in (
            VerificationState.PASSED,
            VerificationState.WARNING,
        )

    @property
    def blocks_delivery(self) -> bool:
        return self.verification_state == VerificationState.FAILED

    # ------------------------------------------------------------------
    # Annotated copies
    # ------------------------------------------------------------------

    def with_evidence(self, *source_ids: str) -> "AgentContextEnvelope":
        """Return a new envelope with evidence_references extended.

        Frozen-dataclass idiom — never mutates the original. Used by
        ``ProvenancePropagationLayer`` (commit 6) to stamp MCP
        source_ids as messages transit the bus.
        """
        merged = tuple(
            dict.fromkeys(  # dedupe, preserve order
                [*self.evidence_references, *source_ids]
            )
        )
        return self.model_copy(update={"evidence_references": merged})

    def with_verification(
        self,
        state: VerificationState,
        *,
        confidence_level: ConfidenceLevel | None = None,
        confidence_value: float | None = None,
    ) -> "AgentContextEnvelope":
        """Return a new envelope with verification state updated."""
        update: dict[str, Any] = {"verification_state": state}
        if confidence_level is not None:
            update["confidence_level"] = confidence_level
        if confidence_value is not None:
            update["confidence_value"] = max(0.0, min(1.0, float(confidence_value)))
        return self.model_copy(update=update)

    def with_delivery(self, status: DeliveryStatus) -> "AgentContextEnvelope":
        return self.model_copy(update={"status": status})

    # ------------------------------------------------------------------
    # Bridging
    # ------------------------------------------------------------------

    def to_message_envelope(self) -> MessageEnvelope:
        """Project onto a legacy ``MessageEnvelope`` for existing handlers.

        Lets interop-aware agents still talk to agents registered on
        the legacy ``communication.MessageBus``. The 3 interop-only
        fields (verification_state / confidence_level /
        biomedical_context_type) are stashed in the payload under
        ``_interop`` so no information is lost.
        """
        payload = dict(self.payload)
        payload["_interop"] = {
            "verification_state": self.verification_state.value,
            "confidence_level": self.confidence_level.value,
            "confidence_value": self.confidence_value,
            "biomedical_context_type": self.biomedical_context_type.value,
            "evidence_references": list(self.evidence_references),
        }
        return MessageEnvelope(
            message_id=self.message_id,
            source_agent=self.originating_agent,
            target_agent=self.target_agent,
            message_type=self.message_type,
            reply_to=self.reply_to,
            payload=payload,
            correlation_id=self.workflow_id,
            causation_id=self.causation_id,
            trace_id=self.trace_id,
            priority=self.priority,
            origin=self.origin,
            timestamp=self.timestamp,
            status=self.status,
        )

    @classmethod
    def from_message_envelope(
        cls,
        envelope: MessageEnvelope,
        *,
        biomedical_context_type: BiomedicalContextType,
    ) -> "AgentContextEnvelope":
        """Lift a legacy envelope into the interop envelope.

        Caller supplies the ``biomedical_context_type`` because the
        legacy envelope doesn't carry it — this keeps the scope
        firewall explicit at lift time.
        """
        interop = envelope.payload.get("_interop", {}) if envelope.payload else {}
        return cls(
            message_id=envelope.message_id,
            originating_agent=envelope.source_agent,
            target_agent=envelope.target_agent,
            message_type=envelope.message_type,
            reply_to=envelope.reply_to,
            payload={
                k: v for k, v in envelope.payload.items() if k != "_interop"
            } if envelope.payload else {},
            workflow_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            trace_id=envelope.trace_id,
            priority=envelope.priority,
            origin=envelope.origin,
            timestamp=envelope.timestamp,
            status=envelope.status,
            verification_state=VerificationState(
                interop.get("verification_state", "pending")
            ),
            confidence_level=ConfidenceLevel(
                interop.get("confidence_level", "moderate")
            ),
            confidence_value=float(interop.get("confidence_value") or 1.0),
            evidence_references=tuple(interop.get("evidence_references") or ()),
            biomedical_context_type=biomedical_context_type,
        )


__all__ = [
    "AgentContextEnvelope",
    "BiomedicalContextType",
    "VerificationState",
    "ConfidenceLevel",
]
