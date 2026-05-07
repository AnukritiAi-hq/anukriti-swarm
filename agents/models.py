"""Anukriti Swarm — Typed interfaces and data models.

Defines the core data structures used across all agents in the swarm.
These models enforce type safety and provide a shared vocabulary for
inter-agent communication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AgentType(str, Enum):
    """Classification of agent roles in the swarm."""

    ORCHESTRATOR = "orchestrator"
    POPULATION = "population"
    CHROMOSOME = "chromosome"
    PHARMACOGENE = "pharmacogene"
    RETRIEVAL = "retrieval"
    VERIFICATION = "verification"
    NARRATIVE = "narrative"


class ExecutionMode(str, Enum):
    """Whether an agent operates deterministically or generatively."""

    DETERMINISTIC = "deterministic"
    GENERATIVE = "generative"
    HYBRID = "hybrid"


class TaskStatus(str, Enum):
    """Lifecycle status of an agent task."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    TIMEOUT = "timeout"


class MessageType(str, Enum):
    """Types of messages exchanged between agents."""

    TASK_ASSIGN = "task_assign"
    TASK_RESULT = "task_result"
    TASK_ERROR = "task_error"
    EVIDENCE_REQUEST = "evidence_request"
    EVIDENCE_RESPONSE = "evidence_response"
    VERIFY_REQUEST = "verify_request"
    VERIFY_RESULT = "verify_result"
    SIGNAL_ABORT = "signal_abort"


class ConfidenceLevel(str, Enum):
    """Confidence classification for outputs."""

    ESTABLISHED = "established"  # Deterministic, source-verified
    HIGH = "high"                # Generative, verified, confidence >= 0.9
    MODERATE = "moderate"        # Generative, verified, confidence >= 0.7
    LOW = "low"                  # Below threshold, flagged
    UNVERIFIED = "unverified"    # Not yet passed verification


@dataclass(frozen=True)
class AgentMessage:
    """Immutable message passed between agents via the memory layer.

    All inter-agent communication uses this structure. Messages are
    never modified after creation — they are append-only in the audit trail.
    """

    message_id: str
    source_agent: str
    target_agent: str | None  # None = broadcast
    message_type: MessageType
    payload: dict[str, Any]
    correlation_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    priority: int = 5  # 0 (highest) to 9 (lowest)


@dataclass
class AgentTask:
    """A unit of work assigned to an agent by the orchestrator.

    Future: Will carry VCF data, gene targets, population context,
    and any upstream results needed for execution.
    """

    task_id: str
    agent_type: AgentType
    parameters: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    timeout_seconds: int = 30


@dataclass
class AgentResult:
    """Structured output from an agent's execution.

    Every result carries provenance metadata for auditability.
    The confidence field is 1.0 for deterministic outputs.
    """

    task_id: str
    agent_id: str
    status: TaskStatus
    output: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    sources: list[str] = field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.DETERMINISTIC
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None


@dataclass
class VariantRecord:
    """A single genomic variant parsed from VCF.

    Future: Will be populated by chromosome agents during VCF ingestion.
    """

    chromosome: str
    position: int
    ref_allele: str
    alt_allele: str
    gene: str | None = None
    rsid: str | None = None
    quality: float | None = None


@dataclass
class PharmacogeneResult:
    """Pharmacogenomic analysis result for a single gene.

    Future: Populated by pharmacogene agents with star alleles,
    phenotype, and drug interaction data.
    """

    gene: str
    diplotype: str | None = None
    phenotype: str | None = None
    drugs_affected: list[str] = field(default_factory=list)
    guideline_source: str | None = None
    confidence: float = 1.0


@dataclass
class PopulationContext:
    """Population-level context for a variant or gene.

    Future: Populated by population agents with allele frequencies
    and population-specific considerations.
    """

    population: str  # e.g., "SAS", "AFR", "EUR"
    allele_frequency: float | None = None
    frequency_source: str | None = None
    is_common: bool | None = None  # freq > 0.01
