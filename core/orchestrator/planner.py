"""``WorkflowPlanner`` — decomposes a query into ordered orchestration substeps.

The planner is the **first generative step** in a GeminiOrchestrator run.
It calls Gemini with the ``orchestration_plan`` prompt to get a JSON
array of ``{step, action, reason}`` objects, validates each action
against the ``ORCHESTRATION_SUBSTEPS`` whitelist, and returns a list of
typed ``PlannedStep`` records.

Because the hackathon demo must work without API access (rate limits,
offline runs, tests), the planner also implements a pure-Python
deterministic fallback that builds a correct plan from the fields on
``SwarmExecutionContext`` alone. The fallback path is indistinguishable
to downstream code except for ``PlannedStep.origin``, which is tagged
``"deterministic"`` vs ``"generative"``.

The planner never makes biomedical claims. It only decides *which
specialists to run and in what order*.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from ai.gemini.client import AIClient
from ai.prompts.templates import (
    ORCHESTRATION_SUBSTEPS,
    orchestration_plan,
)
from core.orchestrator.boundary import (
    DEFAULT_BOUNDARY,
    GenerativeAction,
    GenerativeBoundary,
    GenerativeBoundaryViolation,
)
from core.orchestrator.context import OrchestrationPhase, SwarmExecutionContext


SUBSTEPS = frozenset(ORCHESTRATION_SUBSTEPS)


@dataclass
class PlannedStep:
    """A single substep produced by the planner."""

    step: int
    action: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"step": self.step, "action": self.action, "reason": self.reason}


@dataclass
class WorkflowPlan:
    """Result of planning.

    Attributes:
        steps: Ordered list of ``PlannedStep`` to execute.
        origin: "generative" when Gemini produced the plan, else
            "deterministic" (fallback).
        model: The model that produced the plan, or "fallback".
        latency_ms: How long the planner took.
        raw: The raw LLM text (for debugging / trace), empty when
            fallback was used.
    """

    steps: list[PlannedStep]
    origin: str
    model: str
    latency_ms: float
    raw: str = ""
    notes: list[str] = field(default_factory=list)


class WorkflowPlanner:
    """Decomposes a ``SwarmExecutionContext`` into an ordered plan.

    Collaborators:
        ai_client: injected so tests can use a stub client.
        boundary:  injected so tests can widen / narrow the policy.
    """

    def __init__(
        self,
        ai_client: AIClient | None = None,
        boundary: GenerativeBoundary | None = None,
    ) -> None:
        self.ai = ai_client or _default_ai_client()
        self.boundary = boundary or DEFAULT_BOUNDARY

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def plan(self, ctx: SwarmExecutionContext) -> WorkflowPlan:
        """Produce an ordered plan for the given context.

        Side effects (intentional):
        - ``ctx.mark_phase(OrchestrationPhase.PLANNING)`` while running,
          ``ROUTING`` on exit (the router phase follows).
        - Appends one ``StepMetric`` to ``ctx.orchestration_trace``
          describing the planning call itself.
        """
        ctx.mark_phase(OrchestrationPhase.PLANNING)
        trace = ctx.ensure_trace()
        t0 = time.perf_counter()

        try:
            self.boundary.guard_planning(ctx)
        except GenerativeBoundaryViolation as exc:
            # Empty context — fall back immediately without calling the LLM.
            ctx.record_error(f"planner: {exc}")
            plan = self._fallback_plan(ctx, note=f"boundary: {exc.reason}")
            self._record_trace(trace, plan, time.perf_counter() - t0)
            ctx.mark_phase(OrchestrationPhase.ROUTING)
            return plan

        prompt_ctx = self._prompt_context(ctx)
        prompt = orchestration_plan(prompt_ctx)

        if not self.ai.available:
            plan = self._fallback_plan(ctx, note="AI client unavailable")
            self._record_trace(trace, plan, time.perf_counter() - t0)
            ctx.mark_phase(OrchestrationPhase.ROUTING)
            return plan

        response = self.ai.generate(prompt, context=prompt_ctx, temperature=0.1, max_tokens=512)
        parsed = self._parse_llm_plan(response.text)

        if parsed is None:
            plan = self._fallback_plan(ctx, note="LLM output did not validate")
            plan.raw = response.text
            self._record_trace(trace, plan, time.perf_counter() - t0)
            ctx.mark_phase(OrchestrationPhase.ROUTING)
            return plan

        plan = WorkflowPlan(
            steps=parsed,
            origin="generative",
            model=response.model,
            latency_ms=response.latency_ms,
            raw=response.text,
        )
        self._ensure_mandatory_steps(ctx, plan)
        self._record_trace(trace, plan, time.perf_counter() - t0)
        ctx.mark_phase(OrchestrationPhase.ROUTING)
        return plan

    # ------------------------------------------------------------------
    # LLM parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_llm_plan(text: str) -> list[PlannedStep] | None:
        """Parse + validate the JSON array the LLM is supposed to return.

        Returns ``None`` on any validation failure — the caller will
        fall back to the deterministic plan.
        """
        if not text:
            return None
        # Strip common wrappers — the LLM sometimes prefixes ```json.
        blob = text.strip()
        m = re.search(r"\[[\s\S]*\]", blob)
        if not m:
            return None
        try:
            raw = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
        if not isinstance(raw, list) or not raw:
            return None

        steps: list[PlannedStep] = []
        for i, item in enumerate(raw, start=1):
            if not isinstance(item, dict):
                return None
            action = str(item.get("action", "")).strip()
            if action not in SUBSTEPS:
                return None
            step = int(item.get("step", i))
            reason = str(item.get("reason", "")).strip()[:200]
            steps.append(PlannedStep(step=step, action=action, reason=reason))
        return steps

    # ------------------------------------------------------------------
    # Deterministic fallback
    # ------------------------------------------------------------------

    def _fallback_plan(self, ctx: SwarmExecutionContext, note: str = "") -> WorkflowPlan:
        """Build a minimal correct plan without calling the LLM.

        Rules (match the ``orchestration_plan`` prompt guarantees):
        - ``population_analysis`` if any population field is set
        - ``pharmacogene_analysis`` if a gene is set
        - ``evidence_retrieval`` always (cheap, grounds downstream synth)
        - ``verification`` always, before narrative_synthesis
        - ``comparative_analysis`` when ctx.is_comparative()
        - ``narrative_synthesis`` always last
        """
        ordered: list[str] = []
        if ctx.population or ctx.populations:
            ordered.append("population_analysis")
        if ctx.gene:
            ordered.append("pharmacogene_analysis")
        ordered.append("evidence_retrieval")
        ordered.append("verification")
        if ctx.is_comparative():
            ordered.append("comparative_analysis")
        ordered.append("narrative_synthesis")

        reasons = {
            "population_analysis": "deterministic lookup of allele frequency and rarity context",
            "pharmacogene_analysis": "CPIC activity score and phenotype inference (deterministic)",
            "evidence_retrieval": "MA-RAG retrieval to ground downstream narrative",
            "verification": "6-check verification gate before any user-facing output",
            "comparative_analysis": "fan-out comparison across populations/drugs",
            "narrative_synthesis": "audience-specific explanation of verified findings",
        }
        steps = [
            PlannedStep(step=i + 1, action=a, reason=reasons[a])
            for i, a in enumerate(ordered)
        ]
        return WorkflowPlan(
            steps=steps,
            origin="deterministic",
            model="fallback",
            latency_ms=0.0,
            notes=[note] if note else [],
        )

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def _ensure_mandatory_steps(self, ctx: SwarmExecutionContext, plan: WorkflowPlan) -> None:
        """Patch an LLM plan so it still satisfies mandatory invariants.

        The LLM is instructed to include verification before synthesis,
        but we don't trust it — re-check and patch if needed.
        """
        actions = [s.action for s in plan.steps]
        changed = False

        if "verification" not in actions:
            plan.steps.append(PlannedStep(step=len(plan.steps) + 1, action="verification",
                                          reason="auto-injected: safety gate"))
            plan.notes.append("injected missing verification step")
            changed = True

        if "narrative_synthesis" not in actions:
            plan.steps.append(PlannedStep(step=len(plan.steps) + 1, action="narrative_synthesis",
                                          reason="auto-injected: audience narrative"))
            plan.notes.append("injected missing narrative_synthesis step")
            changed = True

        if ctx.is_comparative() and "comparative_analysis" not in actions:
            # Insert just before narrative_synthesis if present.
            insert_at = next(
                (i for i, s in enumerate(plan.steps) if s.action == "narrative_synthesis"),
                len(plan.steps),
            )
            plan.steps.insert(
                insert_at,
                PlannedStep(step=insert_at + 1, action="comparative_analysis",
                            reason="auto-injected: comparative run"),
            )
            plan.notes.append("injected missing comparative_analysis step")
            changed = True

        if changed:
            # Renumber steps after mutation so the trace stays readable.
            for i, s in enumerate(plan.steps, start=1):
                s.step = i

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _prompt_context(ctx: SwarmExecutionContext) -> dict[str, Any]:
        """Shape context for the ``orchestration_plan`` prompt."""
        return {
            "query": ctx.query,
            "gene": ctx.gene,
            "diplotype": ctx.genotype.get(ctx.gene, ""),
            "drug": ctx.drug,
            "drugs": ctx.drugs,
            "population": ctx.population,
            "populations": ctx.populations,
        }

    @staticmethod
    def _record_trace(trace, plan: WorkflowPlan, elapsed_s: float) -> None:
        trace.record_step(
            "plan",
            origin="generative" if plan.origin == "generative" else "deterministic",
            duration_ms=elapsed_s * 1000,
            status="success",
            plan_size=len(plan.steps),
            model=plan.model,
            actions=[s.action for s in plan.steps],
            notes=plan.notes,
        )
        if plan.origin == "generative":
            # Keep the LLM's reasoning as the high-level summary.
            trace.reasoning_summary = plan.raw[:600]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _default_ai_client() -> AIClient:
    """Pick a working AI client without requiring callers to know the keys.

    Mirrors the logic in ``ADKOrchestrator`` but kept local so this
    module has no cross-package dependency on the ADK integration.
    """
    import os

    from ai.gemini.client import AIProvider

    if os.environ.get("OPENAI_API_KEY"):
        return AIClient(AIProvider.OPENAI)
    return AIClient(AIProvider.GEMINI)


__all__ = ["PlannedStep", "WorkflowPlan", "WorkflowPlanner"]
