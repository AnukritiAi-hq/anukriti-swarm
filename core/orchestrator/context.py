"""``SwarmExecutionContext`` — the orchestrator's working memory.

This is a Pydantic model that flows through the orchestration framework
(planner → router → coordinator → boundary) carrying everything any
orchestration step might need to read or update.

It deliberately lives next to, not replaces, the existing
``core.state.execution.PipelineState``:

- ``PipelineState``            — state for the 7-stage **biomedical** sub-pipeline
  (variants, phenotypes, recommendations, evidence, …). Owned by
  ``workflows.pipeline.run_pipeline``.
- ``SwarmExecutionContext``    — state for the **orchestration** layer one level
  above (query intent, active agents, trace, verification verdict,
  escalation flags). Owned by the GeminiOrchestrator.

Keeping them separate means:
  • The deterministic sub-pipeline can run standalone without dragging in
    any orchestration primitives.
  • The orchestrator can coordinate multiple sub-pipelines (e.g. one per
    population for comparative runs) without PipelineState growing a
    bunch of cross-cutting fields.

The context is immutable-by-convention: most fields use ``default_factory``
and are replaced via ``model_copy(update=…)``. Two convenience mutators
(``activate_agent``, ``attach_trace_step``) are provided for the common
append-only paths so callers don't have to copy the whole model.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from core.orchestrator.trace import OrchestrationTrace


class OrchestrationPhase(str, Enum):
    """High-level phase of the orchestration lifecycle.

    Tracked separately from ``PipelineStage`` because the orchestrator
    wraps the pipeline and also performs planning and synthesis around it.
    """

    RECEIVED = "received"          # Query ingested, context built
    PLANNING = "planning"          # Gemini decomposing into substeps
    ROUTING = "routing"            # AgentRouter selecting specialists
    EXECUTING = "executing"        # Deterministic pipeline running
    VERIFYING = "verifying"        # Verification in progress
    SYNTHESIZING = "synthesizing"  # Gemini composing explanations
    COMPLETE = "complete"
    FAILED = "failed"
    ESCALATED = "escalated"        # Routed to human review


class VerificationState(str, Enum):
    """Simplified verification verdict for the orchestrator.

    Mirrors what the ``verification.engine`` returns but compressed to
    the subset the orchestrator uses to decide escalation and synthesis.
    """

    PENDING = "pending"
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


class SwarmExecutionContext(BaseModel):
    """Working memory for a single orchestration run.

    Every field is optional/defaulted so callers can build a minimal
    context and let the orchestrator fill the rest in as it progresses.
    """

    # --- identity ---
    correlation_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex[:12],
        description="Short unique id, propagated into pipeline + MCP traces.",
    )

    # --- query / input ---
    query: str = Field("", description="Natural-language query or intent string.")
    gene: str = ""
    drug: str = ""
    population: str = ""
    genotype: dict[str, str] = Field(
        default_factory=dict,
        description="Per-gene diplotype, e.g. {'CYP2C19': '*2/*2'}.",
    )
    # For multi-population / multi-drug runs the orchestrator fans out
    # by populating these; single-run mode leaves them empty.
    populations: list[str] = Field(default_factory=list)
    drugs: list[str] = Field(default_factory=list)

    # --- active agents (populated by the router) ---
    active_agents: list[str] = Field(
        default_factory=list,
        description="Agent IDs currently in play for this run.",
    )

    # --- results (populated by the coordinator) ---
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="Citation IDs (PMIDs, CPIC guideline IDs) carried forward.",
    )
    deterministic_results: dict[str, Any] = Field(
        default_factory=dict,
        description="Raw outputs from each deterministic agent/stage.",
    )

    # --- verification + trace ---
    verification_state: VerificationState = VerificationState.PENDING
    verification_report: dict[str, Any] = Field(default_factory=dict)
    orchestration_trace: OrchestrationTrace | None = None

    # --- lifecycle ---
    phase: OrchestrationPhase = OrchestrationPhase.RECEIVED
    errors: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    model_config = {"arbitrary_types_allowed": True}

    # -----------------------------
    # Append-only convenience mutators
    # -----------------------------

    def activate_agent(self, agent_id: str) -> None:
        """Mark an agent as active (idempotent, preserves order)."""
        if agent_id not in self.active_agents:
            self.active_agents.append(agent_id)

    def add_evidence(self, citation_id: str) -> None:
        """Record a citation id, de-duplicated."""
        if citation_id and citation_id not in self.evidence_refs:
            self.evidence_refs.append(citation_id)

    def record_error(self, message: str) -> None:
        """Append an error string (for non-fatal diagnostics)."""
        self.errors.append(message)

    def ensure_trace(self) -> OrchestrationTrace:
        """Lazily create an ``OrchestrationTrace`` bound to this context."""
        if self.orchestration_trace is None:
            self.orchestration_trace = OrchestrationTrace(
                correlation_id=self.correlation_id,
                query=self.query or self._synthesize_query(),
            )
        return self.orchestration_trace

    def mark_phase(self, phase: OrchestrationPhase) -> None:
        self.phase = phase
        if phase in (OrchestrationPhase.COMPLETE, OrchestrationPhase.FAILED):
            self.completed_at = datetime.now(timezone.utc)

    # -----------------------------
    # Helpers
    # -----------------------------

    def _synthesize_query(self) -> str:
        """Build a reasonable query string when the caller didn't provide one."""
        parts: list[str] = []
        if self.gene:
            diplo = self.genotype.get(self.gene, "")
            parts.append(f"{self.gene} {diplo}".strip())
        if self.drug:
            parts.append(f"+ {self.drug}")
        if self.population:
            parts.append(f"in {self.population}")
        return " ".join(parts).strip()

    def is_comparative(self) -> bool:
        """Orchestrator needs to fan out across populations or drugs."""
        return bool(self.populations) or bool(self.drugs)

    def summary(self) -> str:
        """Compact, human-readable status line for logs and demos."""
        q = self.query or self._synthesize_query() or "(empty)"
        return (
            f"[{self.correlation_id}] phase={self.phase.value} "
            f"verify={self.verification_state.value} "
            f"agents={len(self.active_agents)} "
            f"evidence={len(self.evidence_refs)} | {q}"
        )


__all__ = [
    "OrchestrationPhase",
    "VerificationState",
    "SwarmExecutionContext",
]
