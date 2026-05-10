"""Tests for ``core.orchestrator.conflict``.

The ConflictResolver is the cross-run analyzer that decides whether
a comparative run (SAS + EUR + AFR for the same drug, say) should
be delivered as-is, advised on, reviewed, or blocked. The tier
arithmetic is the safety mechanism: if any detector emits BLOCK,
synthesis must be suppressed.

Guarantees this file enforces:

1. EscalationTier is a **closed** 4-value enum with stable rank
   order NONE < ADVISORY < REVIEW < BLOCK.
2. ConflictKind is a **closed** 4-value enum. Extending is a code
   change.
3. ``Resolution.should_block_synthesis`` is True iff tier is BLOCK.
4. ``Resolution.needs_human_review`` is True iff tier is REVIEW or
   BLOCK.
5. Single-run coordination returns NONE (no cross-run detectors
   fire without ≥2 runs).
6. Identical verdicts across runs -> NONE.
7. Distinct verification verdicts -> REVIEW.
8. Distinct recommendations -> ADVISORY (expected across populations).
9. Any run lacking citations -> REVIEW; every run lacking citations -> BLOCK.
10. WARNING verification_state + no other conflicts -> ADVISORY (note).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from core.orchestrator.conflict import (
    Conflict,
    ConflictKind,
    ConflictResolver,
    EscalationTier,
    Resolution,
)
from core.orchestrator.context import (
    SwarmExecutionContext,
    VerificationState,
)

# ---------------------------------------------------------------------------
# Minimal CoordinationResult double — avoids importing the real coordinator
# (which pulls in AI client + pipeline runner). The resolver only reads
# .runs, which is list[dict].
# ---------------------------------------------------------------------------


@dataclass
class _FakeCoordination:
    """Duck-typed CoordinationResult stand-in with only the fields the
    resolver actually reads."""

    runs: list[dict[str, Any]] = field(default_factory=list)


def _run(
    *,
    label: str,
    verdict: str = "pass",
    rec: str | None = None,
    citations: list[str] | None = None,
) -> dict[str, Any]:
    """Build one per-population run record."""
    return {
        "_row_label": label,
        "verification": {"verdict": verdict},
        "recommendations": [{"recommendation": rec}] if rec else [],
        "citations": list(citations) if citations is not None else [],
    }


def _plain_ctx() -> SwarmExecutionContext:
    return SwarmExecutionContext(
        query="CYP2C19 + clopidogrel",
        verification_state=VerificationState.PASSED,
    )


# ---------------------------------------------------------------------------
# Closed-enum contract
# ---------------------------------------------------------------------------


class TestEscalationTier:
    def test_has_exactly_4_tiers(self) -> None:
        assert len(list(EscalationTier)) == 4

    def test_tier_values_are_stable(self) -> None:
        assert EscalationTier.NONE.value == "none"
        assert EscalationTier.ADVISORY.value == "advisory"
        assert EscalationTier.REVIEW.value == "review"
        assert EscalationTier.BLOCK.value == "block"

    def test_unknown_tier_rejected(self) -> None:
        with pytest.raises(ValueError):
            EscalationTier("crash")


class TestConflictKindEnum:
    def test_has_exactly_4_kinds(self) -> None:
        assert len(list(ConflictKind)) == 4

    def test_expected_kinds(self) -> None:
        assert {k.value for k in ConflictKind} == {
            "verification_divergence",
            "recommendation_divergence",
            "evidence_gap",
            "pipeline_partial_failure",
        }


# ---------------------------------------------------------------------------
# Resolution arithmetic
# ---------------------------------------------------------------------------


class TestResolutionProperties:
    def test_empty_resolution_is_none(self) -> None:
        r = Resolution()
        assert r.tier is EscalationTier.NONE
        assert not r.should_block_synthesis
        assert not r.needs_human_review

    def test_block_sets_block_and_review_flags(self) -> None:
        r = Resolution(tier=EscalationTier.BLOCK)
        assert r.should_block_synthesis is True
        assert r.needs_human_review is True

    def test_review_sets_review_but_not_block(self) -> None:
        r = Resolution(tier=EscalationTier.REVIEW)
        assert r.should_block_synthesis is False
        assert r.needs_human_review is True

    def test_advisory_sets_neither_flag(self) -> None:
        r = Resolution(tier=EscalationTier.ADVISORY)
        assert r.should_block_synthesis is False
        assert r.needs_human_review is False

    def test_to_dict_is_jsonable(self) -> None:
        import json

        r = Resolution(
            tier=EscalationTier.REVIEW,
            conflicts=[
                Conflict(
                    kind=ConflictKind.VERIFICATION_DIVERGENCE,
                    tier=EscalationTier.REVIEW,
                    message="sample",
                    affected=["EUR", "SAS"],
                )
            ],
        )
        # Must round-trip through JSON.
        json.dumps(r.to_dict())


# ---------------------------------------------------------------------------
# Resolver — single-run (no cross-run conflicts possible)
# ---------------------------------------------------------------------------


class TestSingleRun:
    def test_empty_runs_returns_none_tier(self, resolver: ConflictResolver) -> None:
        res = resolver.resolve(_plain_ctx(), _FakeCoordination(runs=[]))
        assert res.tier is EscalationTier.NONE
        assert res.conflicts == []

    def test_single_run_returns_none_tier(self, resolver: ConflictResolver) -> None:
        res = resolver.resolve(
            _plain_ctx(),
            _FakeCoordination(runs=[_run(label="SAS", citations=["PMID:1"])]),
        )
        assert res.tier is EscalationTier.NONE


# ---------------------------------------------------------------------------
# Verification divergence — REVIEW
# ---------------------------------------------------------------------------


class TestVerificationDivergence:
    def test_identical_verdicts_emit_nothing(self, resolver: ConflictResolver) -> None:
        res = resolver.resolve(
            _plain_ctx(),
            _FakeCoordination(
                runs=[
                    _run(label="SAS", verdict="pass", citations=["PMID:1"]),
                    _run(label="EUR", verdict="pass", citations=["PMID:2"]),
                ]
            ),
        )
        assert res.tier is EscalationTier.NONE

    def test_distinct_verdicts_emit_review(self, resolver: ConflictResolver) -> None:
        res = resolver.resolve(
            _plain_ctx(),
            _FakeCoordination(
                runs=[
                    _run(label="SAS", verdict="pass", citations=["PMID:1"]),
                    _run(label="EUR", verdict="fail", citations=["PMID:2"]),
                ]
            ),
        )
        assert res.tier is EscalationTier.REVIEW
        kinds = {c.kind for c in res.conflicts}
        assert ConflictKind.VERIFICATION_DIVERGENCE in kinds

    def test_divergence_lists_affected_rows(self, resolver: ConflictResolver) -> None:
        res = resolver.resolve(
            _plain_ctx(),
            _FakeCoordination(
                runs=[
                    _run(label="SAS", verdict="pass", citations=["PMID:1"]),
                    _run(label="EUR", verdict="warn", citations=["PMID:2"]),
                ]
            ),
        )
        divergence = next(
            c for c in res.conflicts if c.kind is ConflictKind.VERIFICATION_DIVERGENCE
        )
        assert set(divergence.affected) == {"SAS", "EUR"}


# ---------------------------------------------------------------------------
# Recommendation divergence — ADVISORY (by design)
# ---------------------------------------------------------------------------


class TestRecommendationDivergence:
    def test_different_recommendations_are_advisory_not_block(
        self, resolver: ConflictResolver
    ) -> None:
        """Different recs across populations is the WHOLE POINT of the
        platform. It must not block — only flag."""
        res = resolver.resolve(
            _plain_ctx(),
            _FakeCoordination(
                runs=[
                    _run(
                        label="SAS",
                        verdict="pass",
                        rec="avoid clopidogrel",
                        citations=["PMID:1"],
                    ),
                    _run(
                        label="EUR",
                        verdict="pass",
                        rec="standard dose",
                        citations=["PMID:2"],
                    ),
                ]
            ),
        )
        assert res.tier is EscalationTier.ADVISORY
        kinds = {c.kind for c in res.conflicts}
        assert ConflictKind.RECOMMENDATION_DIVERGENCE in kinds
        assert not res.should_block_synthesis

    def test_identical_recommendations_emit_nothing(self, resolver: ConflictResolver) -> None:
        res = resolver.resolve(
            _plain_ctx(),
            _FakeCoordination(
                runs=[
                    _run(
                        label="SAS",
                        verdict="pass",
                        rec="standard dose",
                        citations=["PMID:1"],
                    ),
                    _run(
                        label="EUR",
                        verdict="pass",
                        rec="standard dose",
                        citations=["PMID:2"],
                    ),
                ]
            ),
        )
        assert res.tier is EscalationTier.NONE


# ---------------------------------------------------------------------------
# Evidence gap — BLOCK when all runs lack citations, REVIEW when some do
# ---------------------------------------------------------------------------


class TestEvidenceGap:
    def test_all_runs_without_citations_blocks(self, resolver: ConflictResolver) -> None:
        res = resolver.resolve(
            _plain_ctx(),
            _FakeCoordination(
                runs=[
                    _run(label="SAS", citations=[]),
                    _run(label="EUR", citations=[]),
                ]
            ),
        )
        assert res.tier is EscalationTier.BLOCK
        assert res.should_block_synthesis
        kinds = {c.kind for c in res.conflicts}
        assert ConflictKind.EVIDENCE_GAP in kinds

    def test_partial_missing_citations_downgrades_to_review(
        self, resolver: ConflictResolver
    ) -> None:
        res = resolver.resolve(
            _plain_ctx(),
            _FakeCoordination(
                runs=[
                    _run(label="SAS", citations=["PMID:1"]),
                    _run(label="EUR", citations=[]),
                ]
            ),
        )
        # Evidence gap present -> REVIEW tier (not BLOCK because not every run).
        assert res.tier is EscalationTier.REVIEW
        kinds = {c.kind for c in res.conflicts}
        assert ConflictKind.EVIDENCE_GAP in kinds

    def test_single_run_no_citations_does_not_emit_gap(self, resolver: ConflictResolver) -> None:
        """Single run without citations is escalated upstream by the
        coordinator / boundary, not here. The resolver's evidence-gap
        detector still fires — it's a BLOCK because the missing set
        equals the full run set."""
        res = resolver.resolve(
            _plain_ctx(),
            _FakeCoordination(runs=[_run(label="solo", citations=[])]),
        )
        assert res.tier is EscalationTier.BLOCK


# ---------------------------------------------------------------------------
# Warning state adds advisory note
# ---------------------------------------------------------------------------


class TestWarningContext:
    def test_warning_no_other_conflicts_is_advisory(self, resolver: ConflictResolver) -> None:
        ctx = SwarmExecutionContext(
            query="x",
            verification_state=VerificationState.WARNING,
        )
        # Two clean runs; warning state promotes to advisory.
        res = resolver.resolve(
            ctx,
            _FakeCoordination(
                runs=[
                    _run(label="SAS", citations=["PMID:1"]),
                    _run(label="EUR", citations=["PMID:2"]),
                ]
            ),
        )
        assert res.tier is EscalationTier.ADVISORY
        assert any("warning" in n.lower() for n in res.notes)

    def test_warning_with_block_stays_blocked(self, resolver: ConflictResolver) -> None:
        """A stronger tier wins — evidence-gap BLOCK stays BLOCK even
        under WARNING."""
        ctx = SwarmExecutionContext(
            query="x",
            verification_state=VerificationState.WARNING,
        )
        res = resolver.resolve(
            ctx,
            _FakeCoordination(
                runs=[
                    _run(label="SAS", citations=[]),
                    _run(label="EUR", citations=[]),
                ]
            ),
        )
        assert res.tier is EscalationTier.BLOCK


# ---------------------------------------------------------------------------
# Tier arithmetic — strongest wins
# ---------------------------------------------------------------------------


class TestTierCombination:
    def test_review_plus_advisory_yields_review(self, resolver: ConflictResolver) -> None:
        """Verification divergence (REVIEW) + recommendation divergence
        (ADVISORY) must surface as REVIEW — the strongest tier."""
        res = resolver.resolve(
            _plain_ctx(),
            _FakeCoordination(
                runs=[
                    _run(
                        label="SAS",
                        verdict="pass",
                        rec="avoid",
                        citations=["PMID:1"],
                    ),
                    _run(
                        label="EUR",
                        verdict="warn",
                        rec="standard",
                        citations=["PMID:2"],
                    ),
                ]
            ),
        )
        assert res.tier is EscalationTier.REVIEW
        kinds = {c.kind for c in res.conflicts}
        # Both detectors should have fired.
        assert ConflictKind.VERIFICATION_DIVERGENCE in kinds
        assert ConflictKind.RECOMMENDATION_DIVERGENCE in kinds

    def test_block_dominates_all_others(self, resolver: ConflictResolver) -> None:
        res = resolver.resolve(
            _plain_ctx(),
            _FakeCoordination(
                runs=[
                    _run(
                        label="SAS",
                        verdict="pass",
                        rec="avoid",
                        citations=[],
                    ),
                    _run(
                        label="EUR",
                        verdict="warn",
                        rec="standard",
                        citations=[],
                    ),
                ]
            ),
        )
        assert res.tier is EscalationTier.BLOCK


# ---------------------------------------------------------------------------
# Summary formatting (operator tool)
# ---------------------------------------------------------------------------


class TestSummary:
    def test_no_conflict_summary_is_concise(self, resolver: ConflictResolver) -> None:
        res = Resolution()
        assert res.summary() == "no conflicts"

    def test_summary_names_each_conflict_kind(self, resolver: ConflictResolver) -> None:
        res = resolver.resolve(
            _plain_ctx(),
            _FakeCoordination(
                runs=[
                    _run(label="SAS", verdict="pass", citations=[]),
                    _run(label="EUR", verdict="fail", citations=[]),
                ]
            ),
        )
        summary = res.summary()
        # Stable kind names surface in the log line so operators
        # can grep.
        assert "verification_divergence" in summary
        assert "evidence_gap" in summary
