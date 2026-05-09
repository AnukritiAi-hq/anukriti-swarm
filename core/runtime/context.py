"""``UnifiedExecutionContext`` — mutable per-run state container.

Phase 1, commit 1 of the Unified Orchestration + Visualization brief.

The context is the single shared object passed through every stage
of the ``SwarmRuntime`` lifecycle (phase 2). Unlike the repository's
frozen audit records (``VerificationTrace``, ``ClaimCoverageAnalysis``,
``EvidenceSufficiencyTrace``), this class IS mutable — it accumulates
state as stages complete. The final ``UnifiedExecutionReport`` (commit
2) is a frozen snapshot taken from the context at the end.

Why mutable + frozen-snapshot rather than a chain of frozen
dataclasses? Because the runtime has too many stages (10+) to chain
cleanly, and because the event stream (phase 2) needs to dispatch
`context_mutated` events from inside each stage — a chain-of-frozens
would force every stage to rebuild the whole envelope.

Scope firewall
--------------
Constructed only via ``UnifiedExecutionContext.new`` which validates
and coerces inputs. The raw ``__init__`` accepts wide types so Python
tooling works, but the ``.new`` factory is the boundary-enforcing
entry point — same pattern as ``BiomedicalQuery.new``.

Input:
    drug        non-empty str, normalised to lowercase
    gene        non-empty str, normalised to uppercase
    population  SuperPopulation enum instance OR canonical 3-letter
                code string (AFR/AMR/EAS/EUR/SAS). Non-canonical
                strings are rejected.
    genotype    optional str; empty defaults to 'unknown'
    question    optional free-form str; unused by the deterministic
                core, passed through for narrative synthesis

State slots (populated by the runtime, read by consumers):

    orchestration_trace   filled by orchestrator stage
    evidence_state        filled by retrieval + sufficiency stages
    graph_state           filled by KG reasoning stage
    verification_state    filled by deterministic verification stage
    uncertainty_state     filled by sufficiency + uncertainty stages
    provenance_state      filled by MCP persistence stage
    activated_agents      filled across stages as each fires

Every slot defaults to ``None`` or ``()`` so a consumer can check
"has stage X run yet?" by testing the field.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.models.population import SuperPopulation


@dataclass
class UnifiedExecutionContext:
    """Mutable per-run state container shared across runtime stages."""

    # ----- Scope keys (set at construction; never modified) -----
    drug: str
    gene: str
    population: SuperPopulation
    genotype: str = "unknown"
    question: str = ""

    # ----- Identity + timing -----
    correlation_id: str = field(
        default_factory=lambda: f"unified_{uuid.uuid4().hex[:12]}"
    )
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ----- State slots (filled progressively by runtime stages) -----
    activated_agents: tuple[str, ...] = ()
    orchestration_trace: dict[str, Any] | None = None
    evidence_state: dict[str, Any] | None = None
    graph_state: dict[str, Any] | None = None
    verification_state: dict[str, Any] | None = None
    uncertainty_state: dict[str, Any] | None = None
    provenance_state: dict[str, Any] | None = None

    # Generative narrative output — set by final stage
    narrative_output: dict[str, str] = field(default_factory=dict)

    # Errors encountered during any stage (non-fatal recorded here;
    # fatal errors raise out of the runtime's run() method)
    errors: tuple[str, ...] = ()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def new(
        cls,
        *,
        drug: str,
        gene: str,
        population: SuperPopulation | str,
        genotype: str = "unknown",
        question: str = "",
        correlation_id: str = "",
    ) -> "UnifiedExecutionContext":
        """Validate + coerce inputs and construct a context."""

        if not drug or not str(drug).strip():
            raise ValueError("UnifiedExecutionContext.drug must be non-empty")
        if not gene or not str(gene).strip():
            raise ValueError("UnifiedExecutionContext.gene must be non-empty")

        if isinstance(population, SuperPopulation):
            pop = population
        elif isinstance(population, str) and population.strip():
            pop = SuperPopulation(population.strip().upper())
        else:
            raise ValueError(
                "UnifiedExecutionContext.population must be a SuperPopulation "
                f"or canonical 3-letter code; got {population!r}"
            )

        kwargs: dict[str, Any] = {
            "drug": str(drug).strip().lower(),
            "gene": str(gene).strip().upper(),
            "population": pop,
            "genotype": str(genotype).strip() or "unknown",
            "question": str(question).strip(),
        }
        if correlation_id:
            kwargs["correlation_id"] = str(correlation_id)
        return cls(**kwargs)

    # ------------------------------------------------------------------
    # Mutation helpers — each records the activated agent deterministically
    # ------------------------------------------------------------------

    def record_agent(self, agent_name: str) -> None:
        """Record an activated agent; dedup against existing list."""

        name = str(agent_name).strip()
        if not name:
            return
        if name in self.activated_agents:
            return
        self.activated_agents = self.activated_agents + (name,)

    def record_error(self, error: str) -> None:
        """Record a non-fatal error. Append-only; no dedup."""

        text = str(error).strip()
        if not text:
            return
        self.errors = self.errors + (text,)

    # ------------------------------------------------------------------
    # Snapshot for serialization
    # ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """JSON-safe dict of the current context state."""

        return {
            "correlation_id": self.correlation_id,
            "drug": self.drug,
            "gene": self.gene,
            "population": self.population.value,
            "genotype": self.genotype,
            "question": self.question,
            "started_at": self.started_at.isoformat(),
            "activated_agents": list(self.activated_agents),
            "orchestration_trace": self.orchestration_trace,
            "evidence_state": self.evidence_state,
            "graph_state": self.graph_state,
            "verification_state": self.verification_state,
            "uncertainty_state": self.uncertainty_state,
            "provenance_state": self.provenance_state,
            "narrative_output": dict(self.narrative_output),
            "errors": list(self.errors),
        }


__all__ = ["UnifiedExecutionContext"]
