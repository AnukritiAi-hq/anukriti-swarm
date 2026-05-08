"""``ExecutionCoordinator`` — runs the routed plan end-to-end.

The coordinator is the engine room of the orchestration framework.
Given a populated ``SwarmExecutionContext`` and the ``RoutingResult``
from the router, it:

1. Executes the deterministic 7-stage ``workflows.pipeline`` (once per
   population for comparative fan-outs).
2. Aggregates deterministic results onto the context
   (``ctx.deterministic_results``, ``ctx.evidence_refs``,
   ``ctx.verification_state``).
3. Records step-level metrics on the ``OrchestrationTrace``.
4. Handles the two "coordinator-owned" plan actions:
   - ``comparative_analysis``  — build a pre-computed comparison table
     from the per-population results. No LLM call here; the LLM only
     produces narrative *about* this table in the next step.
   - ``narrative_synthesis``   — call ``AIClient`` with
     ``orchestration_synthesis`` (and optionally
     ``orchestration_comparative``) prompts. Guarded by
     ``GenerativeBoundary.guard_synthesis`` so synthesis cannot happen
     before verification passes and without evidence backing.
5. Translates verification failures and boundary violations into
   escalation events (``ctx.phase = ESCALATED``). The orchestrator
   surfaces those to the caller.

What the coordinator is **not**:

- It never produces a biomedical fact itself. Phenotypes, activity
  scores, and recommendations come straight from the deterministic
  pipeline. The coordinator only *packages* them.
- It never bypasses verification. Synthesis is strictly gated.

Collaborators are all injectable so the coordinator can be unit tested
with stubs (a fake pipeline runner, a fake AI client).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from ai.gemini.client import AIClient
from ai.prompts.templates import (
    orchestration_comparative,
    orchestration_synthesis,
)
from core.orchestrator.boundary import (
    DEFAULT_BOUNDARY,
    GenerativeAction,
    GenerativeBoundary,
    GenerativeBoundaryViolation,
)
from core.orchestrator.conflict import (
    ConflictResolver,
    EscalationTier,
    Resolution,
)
from core.orchestrator.context import (
    OrchestrationPhase,
    SwarmExecutionContext,
    VerificationState,
)
from core.orchestrator.router import RoutingResult


# Signature of the deterministic pipeline entry point. Keeping it as a
# ``Callable`` alias means tests can swap in a fake without importing
# the real workflows module.
PipelineRunner = Callable[[dict[str, Any]], tuple[dict[str, Any], Any]]


@dataclass
class CoordinationResult:
    """Aggregate return value from ``ExecutionCoordinator.execute``."""

    # Per-run (or per-population, for comparative) deterministic state.
    runs: list[dict[str, Any]] = field(default_factory=list)

    # Pre-computed rows for the comparative prompt (empty in single-run mode).
    comparison_rows: list[dict[str, Any]] = field(default_factory=list)

    # Audience-keyed synthesis narratives ("audit", "comparative").
    narratives: dict[str, str] = field(default_factory=dict)

    # Escalation reason, if the coordinator tripped the escalation path.
    escalation_reason: str = ""

    # Cross-run conflict analysis (populated after pipeline + verification,
    # before synthesis). ``None`` in single-run mode where conflicts
    # cannot be detected by definition.
    resolution: Resolution | None = None

    # Total coordinator wall time (all phases, not just LLM).
    duration_ms: float = 0.0


class ExecutionCoordinator:
    """Executes the routed plan.

    Parameters
    ----------
    ai_client:
        Injectable. Falls back to the module default (provider-detecting)
        when not supplied.
    boundary:
        Runtime guard for generative actions; ``DEFAULT_BOUNDARY`` by default.
    pipeline_runner:
        Injectable; defaults to ``workflows.pipeline.run_pipeline`` via
        lazy import (so tests don't have to stub the whole workflows
        package).
    """

    def __init__(
        self,
        ai_client: AIClient | None = None,
        boundary: GenerativeBoundary | None = None,
        pipeline_runner: PipelineRunner | None = None,
        conflict_resolver: ConflictResolver | None = None,
    ) -> None:
        self.ai = ai_client or _default_ai_client()
        self.boundary = boundary or DEFAULT_BOUNDARY
        self._runner = pipeline_runner
        self.resolver = conflict_resolver or ConflictResolver()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def execute(
        self, ctx: SwarmExecutionContext, routing: RoutingResult
    ) -> CoordinationResult:
        """Run every planned action in order.

        Side effects:
          - phase transitions (EXECUTING → VERIFYING → SYNTHESIZING → COMPLETE
            or ESCALATED/FAILED).
          - StepMetrics appended to the orchestration trace.
          - ctx.deterministic_results, ctx.evidence_refs,
            ctx.verification_state, ctx.verification_report updated.
        """
        trace = ctx.ensure_trace()
        wall = time.perf_counter()
        result = CoordinationResult()

        # 1. Pipeline execution(s) — happens regardless of planned order
        #    because the pharmacogene/population/retrieval/verification
        #    substeps are all produced by a single pipeline run. We let
        #    the plan order still drive metric *names*, but the actual
        #    compute is one pipeline invocation per (population) row.
        if not self._execute_pipeline(ctx, result):
            # Fatal pipeline error → escalate and stop.
            self._escalate(ctx, trace, reason="pipeline execution failed")
            result.duration_ms = (time.perf_counter() - wall) * 1000
            result.escalation_reason = "pipeline execution failed"
            return result

        # 2. Mark VERIFYING phase and propagate verification state
        ctx.mark_phase(OrchestrationPhase.VERIFYING)
        verified = self._propagate_verification(ctx, result)
        if not verified:
            self._escalate(
                ctx,
                trace,
                reason=f"verification verdict={ctx.verification_state.value}",
            )
            result.escalation_reason = (
                f"verification_state={ctx.verification_state.value}"
            )
            result.duration_ms = (time.perf_counter() - wall) * 1000
            return result

        # 3. Cross-run conflict analysis (pure, cheap)
        self._resolve_conflicts(ctx, result)
        if result.resolution and result.resolution.should_block_synthesis:
            reason = f"conflict blocked synthesis: {result.resolution.summary()}"
            self._escalate(ctx, trace, reason=reason)
            result.escalation_reason = reason
            result.duration_ms = (time.perf_counter() - wall) * 1000
            return result

        # 4. Comparative analysis (deterministic aggregation)
        if any(d.step.action == "comparative_analysis" for d in routing.decisions):
            self._build_comparison_rows(ctx, result)

        # 5. Narrative synthesis (generative — boundary-guarded)
        if any(d.step.action == "narrative_synthesis" for d in routing.decisions):
            ctx.mark_phase(OrchestrationPhase.SYNTHESIZING)
            self._synthesize(ctx, result)

        ctx.mark_phase(OrchestrationPhase.COMPLETE)
        result.duration_ms = (time.perf_counter() - wall) * 1000
        trace.mark_complete(result.duration_ms)
        return result

    # ------------------------------------------------------------------
    # Step 2.5 — Cross-run conflict resolution
    # ------------------------------------------------------------------

    def _resolve_conflicts(
        self, ctx: SwarmExecutionContext, result: CoordinationResult
    ) -> None:
        """Run the conflict resolver and append a trace step.

        Populates ``result.resolution``. BLOCK tier is honored by the
        caller (``execute``); ADVISORY and REVIEW tiers are recorded
        but allow synthesis to proceed — the narratives will surface
        them to the human reader.
        """
        trace = ctx.ensure_trace()
        t0 = time.perf_counter()
        resolution = self.resolver.resolve(ctx, result)
        result.resolution = resolution

        tier_to_status = {
            EscalationTier.NONE: "success",
            EscalationTier.ADVISORY: "success",
            EscalationTier.REVIEW: "warning",
            EscalationTier.BLOCK: "error",
        }
        trace.record_step(
            "conflict_resolution",
            origin="deterministic",
            duration_ms=(time.perf_counter() - t0) * 1000,
            status=tier_to_status[resolution.tier],
            tier=resolution.tier.value,
            conflicts=[c.to_dict() for c in resolution.conflicts],
            notes=resolution.notes,
        )

    # ------------------------------------------------------------------
    # Step 1 — Pipeline execution
    # ------------------------------------------------------------------

    def _execute_pipeline(
        self, ctx: SwarmExecutionContext, result: CoordinationResult
    ) -> bool:
        """Run one deterministic pipeline per population (fan-out if comparative).

        Returns True on success, False if *all* runs errored (fatal).
        Partial failures (one run of a fan-out fails) are recorded but
        not fatal — the surviving runs proceed to verification.
        """
        trace = ctx.ensure_trace()
        runner = self._runner or _default_runner()

        rows = self._fanout_rows(ctx)
        ok_count = 0

        for row in rows:
            t0 = time.perf_counter()
            try:
                state, pipeline_trace = runner(row["seed_state"])
            except Exception as exc:  # pragma: no cover — defensive
                duration = (time.perf_counter() - t0) * 1000
                trace.record_step(
                    f"execute:pipeline[{row['label']}]",
                    origin="deterministic",
                    duration_ms=duration,
                    status="error",
                    error=str(exc),
                )
                ctx.record_error(f"pipeline[{row['label']}]: {exc}")
                continue

            duration = (time.perf_counter() - t0) * 1000
            trace.record_step(
                f"execute:pipeline[{row['label']}]",
                origin="deterministic",
                duration_ms=duration,
                status="warning" if state.get("errors") else "success",
                stages=len(pipeline_trace.stages) if pipeline_trace else 0,
                total_ms=pipeline_trace.total_duration_ms if pipeline_trace else 0,
            )
            state["_row_label"] = row["label"]
            result.runs.append(state)
            ok_count += 1

            # Fold evidence citations into the orchestration context so
            # downstream boundary/synthesis checks see them.
            for cit in state.get("citations", []) or []:
                ctx.add_evidence(cit)

        # Single-run mode: also keep the "principal" deterministic result
        # at a convenient key for downstream readers.
        if result.runs:
            ctx.deterministic_results["principal"] = result.runs[0]
            ctx.deterministic_results["all_runs"] = result.runs

        return ok_count > 0

    def _fanout_rows(self, ctx: SwarmExecutionContext) -> list[dict[str, Any]]:
        """Build the list of pipeline seed-states.

        For a plain single-run context this returns exactly one row.
        For a multi-population context it fans out across ``ctx.populations``
        keeping every other input field identical.

        NB: multi-drug fan-out is handled the same way but by ``drugs``
        instead of ``populations``; the coordinator supports one
        dimension at a time to keep combinatorics sane.
        """
        diplotype = ctx.genotype.get(ctx.gene, "")
        if "/" in diplotype:
            allele1, allele2 = diplotype.split("/", 1)
        else:
            allele1 = allele2 = "*1"

        def _seed(pop: str, drug: str) -> dict[str, Any]:
            return {
                "gene": ctx.gene,
                "drug": drug,
                "population": pop,
                "allele1": allele1,
                "allele2": allele2,
                "correlation_id": f"{ctx.correlation_id}:{pop}:{drug}",
            }

        if ctx.populations:
            return [
                {"label": f"pop={p}", "seed_state": _seed(p, ctx.drug)}
                for p in ctx.populations
            ]
        if ctx.drugs:
            return [
                {"label": f"drug={d}", "seed_state": _seed(ctx.population, d)}
                for d in ctx.drugs
            ]
        return [
            {
                "label": "single",
                "seed_state": _seed(ctx.population, ctx.drug),
            }
        ]

    # ------------------------------------------------------------------
    # Step 2 — Verification propagation
    # ------------------------------------------------------------------

    def _propagate_verification(
        self, ctx: SwarmExecutionContext, result: CoordinationResult
    ) -> bool:
        """Fold the weakest verification verdict across runs onto the context."""
        if not result.runs:
            ctx.verification_state = VerificationState.FAILED
            return False

        verdicts: list[str] = []
        reports: list[dict[str, Any]] = []
        for run in result.runs:
            v = run.get("verification") or {}
            verdicts.append(str(v.get("verdict", "")).lower())
            reports.append(v)

        # Weakest wins: FAILED > WARNING > PASSED.
        if any(v in ("fail", "failed") for v in verdicts):
            ctx.verification_state = VerificationState.FAILED
        elif any(v in ("warn", "warning") for v in verdicts):
            ctx.verification_state = VerificationState.WARNING
        elif all(v in ("pass", "passed") for v in verdicts):
            ctx.verification_state = VerificationState.PASSED
        else:
            ctx.verification_state = VerificationState.PENDING

        ctx.verification_report = {
            "verdicts": verdicts,
            "per_run": reports,
        }

        trace = ctx.ensure_trace()
        trace.record_step(
            "verify:aggregate",
            origin="deterministic",
            duration_ms=0.0,
            status="success" if ctx.verification_state is VerificationState.PASSED
            else "warning" if ctx.verification_state is VerificationState.WARNING
            else "error",
            state=ctx.verification_state.value,
            runs=len(result.runs),
        )

        return ctx.verification_state in (
            VerificationState.PASSED,
            VerificationState.WARNING,
        )

    # ------------------------------------------------------------------
    # Step 3 — Comparative aggregation (pre-LLM, deterministic)
    # ------------------------------------------------------------------

    def _build_comparison_rows(
        self, ctx: SwarmExecutionContext, result: CoordinationResult
    ) -> None:
        """Flatten per-run deterministic output into narrative-ready rows.

        The rows are consumed by ``orchestration_comparative`` so Gemini
        narrates *only* from pre-computed values — no invention possible.
        """
        trace = ctx.ensure_trace()
        t0 = time.perf_counter()

        rows: list[dict[str, Any]] = []
        for run in result.runs:
            pgx = run.get("pharmacogene_result") or {}
            pop = run.get("population_result") or {}
            recs = run.get("recommendations") or []
            rows.append(
                {
                    "label": run.get("_row_label", "?"),
                    "population": pop.get("population") or run.get("population") or "",
                    "drug": run.get("drug", ""),
                    "phenotype": pgx.get("phenotype") or "—",
                    "risk": pgx.get("risk") or "—",
                    "frequency": pop.get("frequency"),
                    "recommendation": recs[0]["recommendation"] if recs else "—",
                }
            )
        result.comparison_rows = rows

        trace.record_step(
            "comparative_analysis",
            origin="deterministic",
            duration_ms=(time.perf_counter() - t0) * 1000,
            status="success",
            rows=len(rows),
        )

    # ------------------------------------------------------------------
    # Step 4 — Narrative synthesis (generative)
    # ------------------------------------------------------------------

    def _synthesize(
        self, ctx: SwarmExecutionContext, result: CoordinationResult
    ) -> None:
        """Produce audit + comparative narratives via the AI client.

        Both calls are wrapped in ``GenerativeBoundary`` guards:
        - ``assert_allowed(EXPLAIN/COMPARE)``
        - ``guard_synthesis(ctx)`` (verification passed + evidence present)
        Boundary violations are recorded and the coordinator marks the
        run ESCALATED, but the non-violating narratives (if any) are kept.
        """
        trace = ctx.ensure_trace()

        # Audit-style synthesis over the principal run
        try:
            self.boundary.assert_allowed(GenerativeAction.EXPLAIN)
            self.boundary.guard_synthesis(ctx)
        except GenerativeBoundaryViolation as exc:
            ctx.record_error(f"synthesis blocked: {exc}")
            self._escalate(ctx, trace, reason=str(exc))
            return

        principal = result.runs[0]
        pgx = principal.get("pharmacogene_result") or {}
        audit_ctx = {
            "gene": ctx.gene or pgx.get("gene", ""),
            "drug": ctx.drug or principal.get("drug", ""),
            "population": ctx.population or (ctx.populations[0] if ctx.populations else ""),
            "phenotype": pgx.get("phenotype", ""),
            "risk": pgx.get("risk", ""),
            "verification": ctx.verification_state.value,
            "confidence": principal.get("verification", {}).get("confidence"),
            "agents": ctx.active_agents,
            "citations": ctx.evidence_refs,
        }

        t0 = time.perf_counter()
        prompt = orchestration_synthesis(audit_ctx)
        response = self.ai.generate(prompt, context=audit_ctx, temperature=0.2, max_tokens=600)
        duration = (time.perf_counter() - t0) * 1000
        result.narratives["audit"] = response.text
        trace.record_step(
            "narrative:audit",
            origin="generative",
            duration_ms=duration,
            status="success",
            model=response.model,
            grounded=response.grounded,
        )

        # Comparative narrative (only if we have rows)
        if result.comparison_rows:
            try:
                self.boundary.assert_allowed(GenerativeAction.COMPARE)
            except GenerativeBoundaryViolation as exc:  # pragma: no cover
                ctx.record_error(f"compare blocked: {exc}")
                return

            comp_ctx = {
                "gene": ctx.gene,
                "drug": ctx.drug,
                "drugs": ctx.drugs,
                "comparison_rows": result.comparison_rows,
            }
            t1 = time.perf_counter()
            prompt = orchestration_comparative(comp_ctx)
            response = self.ai.generate(prompt, context=comp_ctx, temperature=0.3, max_tokens=700)
            duration = (time.perf_counter() - t1) * 1000
            result.narratives["comparative"] = response.text
            trace.record_step(
                "narrative:comparative",
                origin="generative",
                duration_ms=duration,
                status="success",
                model=response.model,
                rows=len(result.comparison_rows),
            )

    # ------------------------------------------------------------------
    # Escalation
    # ------------------------------------------------------------------

    def _escalate(self, ctx: SwarmExecutionContext, trace, reason: str) -> None:
        """Mark the run as escalated and record a trace step."""
        ctx.mark_phase(OrchestrationPhase.ESCALATED)
        trace.record_step(
            "escalate",
            origin="deterministic",
            duration_ms=0.0,
            status="error",
            reason=reason,
        )


# ---------------------------------------------------------------------------
# Lazy defaults
# ---------------------------------------------------------------------------


def _default_ai_client() -> AIClient:
    """Provider detection identical to the planner default."""
    import os

    from ai.gemini.client import AIProvider

    if os.environ.get("OPENAI_API_KEY"):
        return AIClient(AIProvider.OPENAI)
    return AIClient(AIProvider.GEMINI)


def _default_runner() -> PipelineRunner:
    """Lazy-import the real pipeline so tests can stub it out cleanly."""
    from workflows.pipeline import run_pipeline

    return run_pipeline


__all__ = [
    "CoordinationResult",
    "ExecutionCoordinator",
    "PipelineRunner",
]
