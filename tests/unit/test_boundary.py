"""Tests for ``core.orchestrator.boundary``.

Guarantees this file enforces (found in ``architecture/deterministic-
generative-boundary.md``):

1. The boundary is a **closed** 9-value enum. Passing a string works
   because it's a str-Enum, but an unknown value MUST fail at
   ``GenerativeAction(...)`` construction.
2. Exactly 5 actions are allowed: PLAN, ROUTE, EXPLAIN, SUMMARIZE,
   COMPARE.
3. Exactly 4 actions are forbidden: INFER_PHENOTYPE,
   OVERRIDE_RECOMMENDATION, BYPASS_VERIFICATION, FABRICATE_CLAIM.
4. ``guard_synthesis`` blocks when verification is PENDING/FAILED
   OR when pending claims exist without evidence.
5. ``guard_planning`` requires a query or one of gene/drug/populations.

These rules are the runtime encoding of the project's top-level
safety contract. Future contributors tempted to soften them should
update this test file in the same commit — if the test silently
gets easier, something has gone wrong.
"""

from __future__ import annotations

import pytest
from core.orchestrator.boundary import (
    ALLOWED_ACTIONS,
    DEFAULT_BOUNDARY,
    GenerativeAction,
    GenerativeBoundary,
    GenerativeBoundaryViolation,
)
from core.orchestrator.context import (
    SwarmExecutionContext,
    VerificationState,
)

# ---------------------------------------------------------------------------
# Closed-enum contract
# ---------------------------------------------------------------------------


class TestGenerativeActionEnum:
    def test_enum_has_exactly_9_members(self) -> None:
        assert len(list(GenerativeAction)) == 9

    def test_allowed_set_is_exactly_5_actions(self) -> None:
        assert (
            frozenset(
                {
                    GenerativeAction.PLAN,
                    GenerativeAction.ROUTE,
                    GenerativeAction.EXPLAIN,
                    GenerativeAction.SUMMARIZE,
                    GenerativeAction.COMPARE,
                }
            )
            == ALLOWED_ACTIONS
        )

    def test_forbidden_actions_are_4(self) -> None:
        forbidden = set(GenerativeAction) - ALLOWED_ACTIONS
        assert forbidden == {
            GenerativeAction.INFER_PHENOTYPE,
            GenerativeAction.OVERRIDE_RECOMMENDATION,
            GenerativeAction.BYPASS_VERIFICATION,
            GenerativeAction.FABRICATE_CLAIM,
        }

    def test_unknown_value_rejected_at_construction(self) -> None:
        with pytest.raises(ValueError):
            GenerativeAction("analyze_ehr_record")

    def test_str_enum_values_are_stable(self) -> None:
        # Wire-compatible values — downstream JSON consumers read these.
        # Changing any string is a breaking change for event streams.
        assert GenerativeAction.PLAN.value == "plan"
        assert GenerativeAction.INFER_PHENOTYPE.value == "infer_phenotype"
        assert GenerativeAction.BYPASS_VERIFICATION.value == "bypass_verification"


# ---------------------------------------------------------------------------
# assert_allowed — the core gate
# ---------------------------------------------------------------------------


class TestAssertAllowed:
    @pytest.mark.parametrize("action", list(ALLOWED_ACTIONS))
    def test_allowed_action_does_not_raise(
        self, boundary: GenerativeBoundary, action: GenerativeAction
    ) -> None:
        # Must be a no-op for every allowed action.
        boundary.assert_allowed(action)

    @pytest.mark.parametrize(
        "action",
        [
            GenerativeAction.INFER_PHENOTYPE,
            GenerativeAction.OVERRIDE_RECOMMENDATION,
            GenerativeAction.BYPASS_VERIFICATION,
            GenerativeAction.FABRICATE_CLAIM,
        ],
    )
    def test_every_forbidden_action_raises(
        self, boundary: GenerativeBoundary, action: GenerativeAction
    ) -> None:
        with pytest.raises(GenerativeBoundaryViolation) as exc_info:
            boundary.assert_allowed(action)
        # The violation exposes the action so the caller can route
        # on it — not just a generic string match.
        assert exc_info.value.action is action

    def test_forbidden_action_message_names_action_value(
        self, boundary: GenerativeBoundary
    ) -> None:
        with pytest.raises(GenerativeBoundaryViolation) as exc_info:
            boundary.assert_allowed(GenerativeAction.INFER_PHENOTYPE)
        # Violation message must include the action value so log-scrapers
        # can categorise without inspecting the exception type.
        assert "infer_phenotype" in str(exc_info.value)

    def test_custom_reason_is_preserved(self, boundary: GenerativeBoundary) -> None:
        with pytest.raises(GenerativeBoundaryViolation) as exc_info:
            boundary.assert_allowed(
                GenerativeAction.FABRICATE_CLAIM,
                reason="caller did not attach evidence",
            )
        assert exc_info.value.reason == "caller did not attach evidence"

    def test_is_allowed_mirrors_assert_allowed(self, boundary: GenerativeBoundary) -> None:
        for action in GenerativeAction:
            expected = action in ALLOWED_ACTIONS
            assert boundary.is_allowed(action) is expected


class TestCustomAllowedSet:
    """Boundary must honour a caller-supplied allow list."""

    def test_custom_allow_list_applied(self) -> None:
        b = GenerativeBoundary(allowed={GenerativeAction.PLAN})
        b.assert_allowed(GenerativeAction.PLAN)
        with pytest.raises(GenerativeBoundaryViolation):
            # EXPLAIN is normally allowed, but the custom list excludes it.
            b.assert_allowed(GenerativeAction.EXPLAIN)

    def test_empty_allow_list_blocks_everything(self) -> None:
        b = GenerativeBoundary(allowed=set())
        for action in GenerativeAction:
            with pytest.raises(GenerativeBoundaryViolation):
                b.assert_allowed(action)


# ---------------------------------------------------------------------------
# guard_synthesis — verification gate + fabricated-claim gate
# ---------------------------------------------------------------------------


def _ctx_with_verification(state: VerificationState, **kwargs) -> SwarmExecutionContext:
    """Build a context with a specified verification state."""
    return SwarmExecutionContext(
        query="CYP2C19 *2/*2 + clopidogrel in SAS",
        verification_state=state,
        **kwargs,
    )


class TestGuardSynthesis:
    def test_passed_with_evidence_does_not_raise(self, boundary: GenerativeBoundary) -> None:
        ctx = _ctx_with_verification(
            VerificationState.PASSED,
            evidence_refs=["CPIC:clopidogrel-CYP2C19-2022"],
        )
        boundary.guard_synthesis(ctx)  # no raise

    def test_pending_blocks_synthesis(self, boundary: GenerativeBoundary) -> None:
        ctx = _ctx_with_verification(VerificationState.PENDING)
        with pytest.raises(GenerativeBoundaryViolation) as exc_info:
            boundary.guard_synthesis(ctx)
        assert exc_info.value.action is GenerativeAction.BYPASS_VERIFICATION

    def test_failed_blocks_synthesis(self, boundary: GenerativeBoundary) -> None:
        ctx = _ctx_with_verification(VerificationState.FAILED)
        with pytest.raises(GenerativeBoundaryViolation) as exc_info:
            boundary.guard_synthesis(ctx)
        assert exc_info.value.action is GenerativeAction.BYPASS_VERIFICATION

    def test_warning_allowed_at_boundary_level(self, boundary: GenerativeBoundary) -> None:
        """WARNING is not a hard block — the coordinator routes it to
        escalation via the ConflictResolver. The boundary only blocks
        PENDING / FAILED."""
        ctx = _ctx_with_verification(
            VerificationState.WARNING,
            evidence_refs=["CPIC:x"],
        )
        boundary.guard_synthesis(ctx)  # no raise

    def test_pending_claims_without_evidence_raises(self, boundary: GenerativeBoundary) -> None:
        ctx = _ctx_with_verification(
            VerificationState.PASSED,
            deterministic_results={"pending_claims": [{"text": "some claim"}]},
            evidence_refs=[],
        )
        with pytest.raises(GenerativeBoundaryViolation) as exc_info:
            boundary.guard_synthesis(ctx)
        assert exc_info.value.action is GenerativeAction.FABRICATE_CLAIM

    def test_pending_claims_with_evidence_passes(self, boundary: GenerativeBoundary) -> None:
        ctx = _ctx_with_verification(
            VerificationState.PASSED,
            deterministic_results={"pending_claims": [{"text": "some claim"}]},
            evidence_refs=["PMID:12345"],
        )
        boundary.guard_synthesis(ctx)  # no raise


# ---------------------------------------------------------------------------
# guard_planning — minimum-context gate
# ---------------------------------------------------------------------------


class TestGuardPlanning:
    def test_query_only_is_sufficient(self, boundary: GenerativeBoundary) -> None:
        ctx = SwarmExecutionContext(query="What drug is safe for a CYP2C19 *2/*2 SAS patient?")
        boundary.guard_planning(ctx)  # no raise

    def test_gene_only_is_sufficient(self, boundary: GenerativeBoundary) -> None:
        ctx = SwarmExecutionContext(gene="CYP2C19")
        boundary.guard_planning(ctx)

    def test_drug_only_is_sufficient(self, boundary: GenerativeBoundary) -> None:
        ctx = SwarmExecutionContext(drug="clopidogrel")
        boundary.guard_planning(ctx)

    def test_populations_only_is_sufficient(self, boundary: GenerativeBoundary) -> None:
        ctx = SwarmExecutionContext(populations=["SAS", "EUR"])
        boundary.guard_planning(ctx)

    def test_empty_context_raises(self, boundary: GenerativeBoundary) -> None:
        ctx = SwarmExecutionContext()
        with pytest.raises(GenerativeBoundaryViolation) as exc_info:
            boundary.guard_planning(ctx)
        assert exc_info.value.action is GenerativeAction.PLAN


# ---------------------------------------------------------------------------
# Module-level default
# ---------------------------------------------------------------------------


class TestDefaultBoundary:
    def test_default_boundary_is_instance(self) -> None:
        assert isinstance(DEFAULT_BOUNDARY, GenerativeBoundary)

    def test_default_boundary_applies_project_policy(self) -> None:
        for action in ALLOWED_ACTIONS:
            assert DEFAULT_BOUNDARY.is_allowed(action)
        for action in set(GenerativeAction) - ALLOWED_ACTIONS:
            assert not DEFAULT_BOUNDARY.is_allowed(action)
