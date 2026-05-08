"""``GenerativeBoundary`` — runtime enforcement of the deterministic/generative split.

The project's ``architecture/deterministic-generative-boundary.md`` states
what Gemini is and is not allowed to do. This module encodes those rules
in code so they are enforced at runtime, not just honored by convention.

What Gemini (the generative layer) **may** do:

- ``PLAN``           — decompose a query into substeps
- ``ROUTE``          — suggest which specialist agents to activate
                       (final decision still belongs to ``AgentRouter``)
- ``EXPLAIN``        — produce audience-specific narrative from already-
                       verified deterministic findings
- ``SUMMARIZE``      — summarize an orchestration run
- ``COMPARE``        — comparative narrative across populations / drugs

What Gemini **may NOT** do (enforced here):

- ``INFER_PHENOTYPE``   — infer a PGx phenotype from genotype
- ``OVERRIDE_RECOMMENDATION`` — change, soften, or contradict a
                                deterministic CPIC recommendation
- ``BYPASS_VERIFICATION`` — emit user-facing content without a
                            ``VerificationState.PASSED`` verdict
- ``FABRICATE_CLAIM``   — make a biomedical claim without a citation
                          already present in ``evidence_refs``

Usage::

    boundary = GenerativeBoundary()
    boundary.assert_allowed(GenerativeAction.PLAN)                   # ok
    boundary.assert_allowed(GenerativeAction.INFER_PHENOTYPE)        # raises
    boundary.guard_synthesis(ctx)  # raises if verification not passed

Violations raise ``GenerativeBoundaryViolation``, which the coordinator
catches and translates into an escalation event rather than crashing the
whole run — but the guard itself is strict by design.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable

from core.orchestrator.context import SwarmExecutionContext, VerificationState


class GenerativeAction(str, Enum):
    """Every action the generative layer might attempt."""

    # ---- allowed ----
    PLAN = "plan"
    ROUTE = "route"
    EXPLAIN = "explain"
    SUMMARIZE = "summarize"
    COMPARE = "compare"

    # ---- disallowed ----
    INFER_PHENOTYPE = "infer_phenotype"
    OVERRIDE_RECOMMENDATION = "override_recommendation"
    BYPASS_VERIFICATION = "bypass_verification"
    FABRICATE_CLAIM = "fabricate_claim"


ALLOWED_ACTIONS: frozenset[GenerativeAction] = frozenset(
    {
        GenerativeAction.PLAN,
        GenerativeAction.ROUTE,
        GenerativeAction.EXPLAIN,
        GenerativeAction.SUMMARIZE,
        GenerativeAction.COMPARE,
    }
)


class GenerativeBoundaryViolation(Exception):
    """Raised when a generative-layer caller attempts a forbidden action."""

    def __init__(self, action: GenerativeAction, reason: str) -> None:
        super().__init__(f"Generative boundary violation [{action.value}]: {reason}")
        self.action = action
        self.reason = reason


class GenerativeBoundary:
    """Runtime guard enforcing the Gemini-layer safety rules.

    Instances are cheap and stateless. Create one per orchestrator or
    share a module-level singleton — both are fine.
    """

    def __init__(self, allowed: Iterable[GenerativeAction] | None = None) -> None:
        # Allow callers (e.g. tests) to override, but default is the
        # project-wide policy from the boundary doc.
        self._allowed: frozenset[GenerativeAction] = (
            frozenset(allowed) if allowed is not None else ALLOWED_ACTIONS
        )

    # ------------------------------------------------------------------
    # Action-level checks
    # ------------------------------------------------------------------

    def is_allowed(self, action: GenerativeAction) -> bool:
        return action in self._allowed

    def assert_allowed(self, action: GenerativeAction, reason: str = "") -> None:
        """Raise ``GenerativeBoundaryViolation`` if ``action`` is forbidden."""
        if action in self._allowed:
            return
        default_reasons = {
            GenerativeAction.INFER_PHENOTYPE: (
                "Phenotype inference must come from the deterministic "
                "pharmacogene agents (CPIC activity score)."
            ),
            GenerativeAction.OVERRIDE_RECOMMENDATION: (
                "CPIC recommendations are authoritative and may not be "
                "softened, rewritten, or contradicted by the LLM."
            ),
            GenerativeAction.BYPASS_VERIFICATION: (
                "User-facing output requires a VerificationState.PASSED "
                "verdict from the verification engine."
            ),
            GenerativeAction.FABRICATE_CLAIM: (
                "Every biomedical claim must reference a citation already "
                "present in the context's evidence_refs."
            ),
        }
        raise GenerativeBoundaryViolation(
            action, reason or default_reasons.get(action, "action not permitted")
        )

    # ------------------------------------------------------------------
    # Context-level checks (used by the coordinator / orchestrator)
    # ------------------------------------------------------------------

    def guard_synthesis(self, ctx: SwarmExecutionContext) -> None:
        """Guard before emitting Gemini-synthesized user-facing content.

        Enforces two rules together:
        1. The verification state must be PASSED. WARNING routes to
           escalation (caller decides); FAILED/PENDING always block.
        2. If the caller has declared claims to synthesize (via
           ``ctx.deterministic_results['pending_claims']``), each must
           be backed by at least one entry in ``ctx.evidence_refs``.
        """
        if ctx.verification_state in (
            VerificationState.PENDING,
            VerificationState.FAILED,
        ):
            raise GenerativeBoundaryViolation(
                GenerativeAction.BYPASS_VERIFICATION,
                f"verification_state={ctx.verification_state.value}; "
                "synthesis requires PASSED",
            )

        pending = ctx.deterministic_results.get("pending_claims") or []
        if pending and not ctx.evidence_refs:
            raise GenerativeBoundaryViolation(
                GenerativeAction.FABRICATE_CLAIM,
                f"{len(pending)} pending claim(s) but evidence_refs is empty",
            )

    def guard_planning(self, ctx: SwarmExecutionContext) -> None:
        """Guard before calling Gemini for planning.

        Planning is always allowed, but we require a minimal context
        (either a query string or enough structured fields to build one)
        so the LLM has something to reason about.
        """
        self.assert_allowed(GenerativeAction.PLAN)
        if not ctx.query and not (ctx.gene or ctx.drug or ctx.populations):
            raise GenerativeBoundaryViolation(
                GenerativeAction.PLAN,
                "empty context; planner needs at least a query or one of "
                "gene/drug/populations",
            )


# Project-wide default. Callers may instantiate their own for tests.
DEFAULT_BOUNDARY = GenerativeBoundary()


__all__ = [
    "GenerativeAction",
    "ALLOWED_ACTIONS",
    "GenerativeBoundaryViolation",
    "GenerativeBoundary",
    "DEFAULT_BOUNDARY",
]
