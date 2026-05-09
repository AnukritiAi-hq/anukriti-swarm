"""``GeminiOrchestrator`` — high-level Gemini-powered orchestrator.

The orchestrator is a thin facade that composes the ``core.orchestrator``
primitives into a single ergonomic entry point for callers:

    orchestrator = GeminiOrchestrator()
    result = orchestrator.run(
        gene="CYP2C19", drug="clopidogrel", population="SAS",
        allele1="*2", allele2="*2",
    )
    print(result.context.summary())
    print(result.narratives["audit"])

Lifecycle (one ``run``):

    1. ContextAssembler   builds SwarmExecutionContext
    2. WorkflowPlanner    produces an ordered plan (Gemini + fallback)
    3. AgentRouter        resolves planner actions to specialist agents
    4. ExecutionCoordinator
                          executes pipeline(s), aggregates verification,
                          synthesizes narratives (boundary-guarded)
    5. OrchestrationResult returned with context, plan, routing,
                          narratives, comparison rows, escalation reason.

Gemini's role here is strictly **orchestration + narration**:

    plan  →  (advisory) route  →  synthesize  →  compare

All biomedical reasoning is performed by the deterministic pipeline.
``GenerativeBoundary`` enforces this at runtime; attempting
phenotype inference, recommendation override, verification bypass,
or unsupported claims raises ``GenerativeBoundaryViolation`` and is
translated into an escalation event.

Convenience methods:

    run(**kwargs)                  # single-query path
    compare_populations(...)       # multi-population fan-out
    compare_drugs(...)             # multi-drug fan-out

All three return the same ``OrchestrationResult`` shape so callers can
handle them uniformly.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ai.gemini.client import AIClient
from agents.registry.registry import AgentRegistry
from core.orchestrator.boundary import GenerativeBoundary
from core.orchestrator.context import (
    OrchestrationPhase,
    SwarmExecutionContext,
    VerificationState,
)
from core.orchestrator.context_assembler import ContextAssembler
from core.orchestrator.coordinator import (
    CoordinationResult,
    ExecutionCoordinator,
    PipelineRunner,
)
from core.orchestrator.planner import WorkflowPlan, WorkflowPlanner
from core.orchestrator.router import AgentRouter, RoutingResult
from core.orchestrator.trace import OrchestrationTrace


@dataclass
class OrchestrationResult:
    """Aggregate return value from any public ``GeminiOrchestrator`` entry point."""

    context: SwarmExecutionContext
    plan: WorkflowPlan
    routing: RoutingResult
    coordination: CoordinationResult
    total_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    prior_runs: dict[str, Any] | None = None

    # --- convenience accessors --------------------------------------------

    @property
    def trace(self) -> OrchestrationTrace:
        assert self.context.orchestration_trace is not None  # ensured by assembler
        return self.context.orchestration_trace

    @property
    def narratives(self) -> dict[str, str]:
        return self.coordination.narratives

    @property
    def comparison_rows(self) -> list[dict[str, Any]]:
        return self.coordination.comparison_rows

    @property
    def escalated(self) -> bool:
        return self.context.phase is OrchestrationPhase.ESCALATED

    @property
    def verification_state(self) -> VerificationState:
        return self.context.verification_state

    def summary(self) -> str:
        """One-paragraph human-readable overview."""
        ctx = self.context
        verdict = ctx.verification_state.value
        n_runs = len(self.coordination.runs)
        return (
            f"[{ctx.correlation_id}] {ctx.query}\n"
            f"  phase={ctx.phase.value} verify={verdict} "
            f"runs={n_runs} agents={len(ctx.active_agents)} "
            f"evidence={len(ctx.evidence_refs)}\n"
            f"  plan={self.plan.origin}({self.plan.model}) "
            f"steps={len(self.plan.steps)} "
            f"narratives={list(self.narratives.keys()) or '—'}\n"
            f"  total={self.total_duration_ms:.1f}ms "
            f"(plan={self.plan.latency_ms:.1f}ms, "
            f"coord={self.coordination.duration_ms:.1f}ms)"
        )


class GeminiOrchestrator:
    """Compose assembler + planner + router + coordinator.

    All collaborators are injectable so tests can supply stubs without
    touching the network. When no arguments are passed, each collaborator
    is instantiated with project defaults (shared AgentRegistry,
    provider-detecting ``AIClient``, real ``workflows.pipeline.run_pipeline``).
    """

    def __init__(
        self,
        *,
        ai_client: AIClient | None = None,
        boundary: GenerativeBoundary | None = None,
        registry: AgentRegistry | None = None,
        pipeline_runner: PipelineRunner | None = None,
        assembler: ContextAssembler | None = None,
        planner: WorkflowPlanner | None = None,
        router: AgentRouter | None = None,
        coordinator: ExecutionCoordinator | None = None,
        memory_advisor: Any = None,
    ) -> None:
        # Shared boundary across planner + coordinator so policy is uniform.
        self.boundary = boundary or GenerativeBoundary()

        self.assembler = assembler or ContextAssembler()
        self.planner = planner or WorkflowPlanner(
            ai_client=ai_client, boundary=self.boundary
        )
        self.router = router or AgentRouter(registry=registry)
        self.coordinator = coordinator or ExecutionCoordinator(
            ai_client=ai_client,
            boundary=self.boundary,
            pipeline_runner=pipeline_runner,
        )
        # Optional memory-aware pre-consultation. Duck-typed: any
        # object exposing ``.consult(gene, drug, population)`` returning
        # an object with ``to_dict()`` works. Typed ``Any`` so
        # core.orchestrator stays free of MCP imports.
        self.memory_advisor = memory_advisor

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def run(
        self,
        *,
        query: str = "",
        gene: str = "",
        drug: str = "",
        population: str = "",
        allele1: str | None = None,
        allele2: str | None = None,
        genotype: dict[str, str] | None = None,
    ) -> OrchestrationResult:
        """Single-query orchestration.

        Call with either a ``query`` string (freeform, parsed by the
        assembler) or structured fields (gene/drug/population/alleles),
        or both — structured fields win.
        """
        if query and not (gene or drug or population):
            ctx = self.assembler.from_query(query)
        else:
            ctx = self.assembler.from_kwargs(
                query=query,
                gene=gene,
                drug=drug,
                population=population,
                allele1=allele1,
                allele2=allele2,
                genotype=genotype,
            )
        return self._drive(ctx)

    def compare_populations(
        self,
        *,
        gene: str,
        drug: str,
        populations: list[str],
        allele1: str,
        allele2: str,
        query: str = "",
    ) -> OrchestrationResult:
        """Fan-out across populations — keep gene+drug+genotype fixed.

        Produces a ``comparative`` narrative in addition to the audit
        summary. ``coordination.comparison_rows`` exposes the structured
        side-by-side data the narrative was built from.
        """
        if not populations:
            raise ValueError("compare_populations requires a non-empty populations list")
        ctx = self.assembler.from_kwargs(
            query=query,
            gene=gene,
            drug=drug,
            populations=populations,
            allele1=allele1,
            allele2=allele2,
        )
        return self._drive(ctx)

    def compare_drugs(
        self,
        *,
        gene: str,
        drugs: list[str],
        population: str,
        allele1: str,
        allele2: str,
        query: str = "",
    ) -> OrchestrationResult:
        """Fan-out across drugs — keep gene+genotype+population fixed."""
        if not drugs:
            raise ValueError("compare_drugs requires a non-empty drugs list")
        ctx = self.assembler.from_kwargs(
            query=query,
            gene=gene,
            drugs=drugs,
            population=population,
            allele1=allele1,
            allele2=allele2,
        )
        return self._drive(ctx)

    # ------------------------------------------------------------------
    # Core driver
    # ------------------------------------------------------------------

    def _drive(self, ctx: SwarmExecutionContext) -> OrchestrationResult:
        """Run the full lifecycle on an already-assembled context."""
        t0 = time.perf_counter()

        prior_runs_dict = self._consult_memory(ctx)

        plan = self.planner.plan(ctx)
        routing = self.router.route(ctx, plan.steps)
        coordination = self.coordinator.execute(ctx, routing)
        total_ms = (time.perf_counter() - t0) * 1000

        # Make sure the trace has a total duration even when the
        # coordinator escalated early.
        trace = ctx.ensure_trace()
        if trace.completed_at is None:
            trace.mark_complete(total_ms)

        return OrchestrationResult(
            context=ctx,
            plan=plan,
            routing=routing,
            coordination=coordination,
            total_duration_ms=total_ms,
            errors=list(ctx.errors),
            prior_runs=prior_runs_dict,
        )

    def _consult_memory(
        self, ctx: SwarmExecutionContext
    ) -> dict[str, Any] | None:
        """Opt-in memory-aware pre-consultation.

        Consulted once at the head of ``_drive`` when a ``memory_advisor``
        was supplied. Records one ``memory.consult`` trace step so the
        read-side of memory-aware orchestration shows up in the same
        observability view as the deterministic pipeline stages.
        Consultation failure is non-fatal — we log to ``ctx.errors``
        and return ``None`` so planning proceeds unchanged.
        """
        if self.memory_advisor is None:
            return None
        t0 = time.perf_counter()
        try:
            digest = self.memory_advisor.consult(
                gene=ctx.gene, drug=ctx.drug, population=ctx.population
            )
            payload = digest.to_dict()
            trace = ctx.ensure_trace()
            trace.record_step(
                "memory.consult",
                origin="system",
                duration_ms=(time.perf_counter() - t0) * 1000,
                status="success",
                **payload,
            )
            return payload
        except Exception as exc:
            ctx.record_error(f"memory_advisor.consult: {exc}")
            return None


__all__ = ["GeminiOrchestrator", "OrchestrationResult"]
