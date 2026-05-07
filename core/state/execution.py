"""LangGraph-compatible execution state schemas.

Defines the typed state that flows through the execution graph.
Uses Pydantic models for validation while maintaining compatibility
with LangGraph's channel-based state update pattern.

Design:
- PipelineState is the top-level state passed between graph nodes
- Each agent reads relevant fields and returns partial updates
- State accumulates results as the pipeline progresses
- Immutable intermediate snapshots enable checkpointing and replay
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from core.models.agents import AuditEntry, EscalationEvent, VerificationReport
from core.models.genomics import GenomicVariant, OriginType, Phenotype
from core.models.pharmacogenomics import Recommendation, RetrievalResult
from core.models.population import PopulationContext


class PipelineStage(str, Enum):
    """Current stage of the execution pipeline."""

    INGESTION = "ingestion"
    ORCHESTRATION = "orchestration"
    CHROMOSOME_ANALYSIS = "chromosome_analysis"
    PHARMACOGENE_ANALYSIS = "pharmacogene_analysis"
    POPULATION_CONTEXT = "population_context"
    EVIDENCE_RETRIEVAL = "evidence_retrieval"
    VERIFICATION = "verification"
    NARRATIVE = "narrative"
    COMPLETE = "complete"
    FAILED = "failed"


class PipelineStatus(str, Enum):
    """Overall pipeline execution status."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineState(BaseModel):
    """Top-level execution state for the LangGraph pipeline.

    This is the shared state object that flows through all graph nodes.
    Each agent reads relevant fields and returns a partial update dict
    that gets merged into the state.

    LangGraph compatibility:
    - Fields act as channels that agents read/write
    - Partial updates are merged (list fields are appended)
    - State can be serialized for checkpointing

    Future: Will support streaming partial results, human-in-the-loop
    interrupts, and branching execution paths.
    """

    # --- Identity ---
    correlation_id: str = Field(..., description="Unique execution run identifier")
    sample_id: str | None = Field(None, description="Patient/sample identifier")
    query: str = Field("", description="Original user query")

    # --- Input ---
    variants: list[GenomicVariant] = Field(default_factory=list)
    target_genes: list[str] = Field(default_factory=list)
    target_chromosomes: list[str] = Field(default_factory=list)
    drug_context: list[str] = Field(default_factory=list, description="Drugs of interest")

    # --- Analysis Results ---
    phenotypes: list[Phenotype] = Field(default_factory=list)
    population_context: PopulationContext | None = None
    recommendations: list[Recommendation] = Field(default_factory=list)
    evidence: list[RetrievalResult] = Field(default_factory=list)

    # --- Verification ---
    verification_reports: list[VerificationReport] = Field(default_factory=list)
    escalations: list[EscalationEvent] = Field(default_factory=list)

    # --- Output ---
    narrative: str = Field("", description="Generated report text")
    citations: list[str] = Field(default_factory=list)

    # --- Execution Metadata ---
    stage: PipelineStage = PipelineStage.PENDING
    status: PipelineStatus = PipelineStatus.PENDING
    errors: list[str] = Field(default_factory=list)
    audit_trail: list[AuditEntry] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    model_config = {"arbitrary_types_allowed": True}


class CheckpointSnapshot(BaseModel):
    """Serializable snapshot of pipeline state for resume-after-failure.

    Captured after each stage completes. Enables:
    - Resume from last successful stage
    - Execution replay for debugging
    - Partial result inspection

    Future: Will support diff-based snapshots for storage efficiency.
    """

    snapshot_id: str
    correlation_id: str
    stage: PipelineStage
    state: PipelineState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"arbitrary_types_allowed": True}
