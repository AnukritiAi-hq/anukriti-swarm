"""Tests for ``core.evidence_sufficiency.sufficiency.decision_engine``.

Every rule in the 12-rule table must be exercisable by a test. The
rules fire in priority order R1..R12 and the first match wins, so
each test constructs the *minimal* coverage shape that isolates one
rule — higher-priority rules must not fire on that shape.

Rule-table contract (from the module docstring):

    R1  hard conflict OR CONFLICT_FREE MISSING -> BLOCK
    R2  PHENOTYPE MISSING                       -> BLOCK
    R3  RECOMMENDATION MISSING                  -> BLOCK
    R4  provenance incomplete                   -> ABSTAIN
    R5  POPULATION MISSING                      -> ESCALATE
    R6  CPIC MISSING                            -> REQUEST_MORE
    R7  ALLELE MISSING                          -> REQUEST_MORE
    R8  RECOMMENDATION UNCERTAIN                -> DOWNGRADE
    R9  POPULATION UNCERTAIN                    -> DOWNGRADE
    R10 any other UNCERTAIN (ALLELE / CPIC / PHENOTYPE / CONFLICT_FREE
        except the ones handled above)          -> DOWNGRADE
    R11 only CONFLICT_FREE UNCERTAIN            -> PASS_WITH_CAVEAT
    R12 all COVERED, no conflict                -> SUFFICIENT

These must stay stable. Changing any rule's outcome is a policy
change that must surface in a commit where this file is also updated.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest
from core.evidence_sufficiency.conflict.agent import (
    ConflictFinding,
    ConflictKind,
    ConflictSeverity,
)
from core.evidence_sufficiency.coverage.claim_coverage import (
    ClaimEvidenceFacet,
    FacetCoverageState,
)
from core.evidence_sufficiency.coverage.provenance_tracker import (
    ALL_DIMENSIONS,
    DimensionState,
    ProvenanceCoverageReport,
)
from core.evidence_sufficiency.sufficiency.decision_engine import (
    SufficiencyDecision,
    SufficiencyDecisionEngine,
)

from tests.conftest import make_analysis_with_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hard_phenotype_conflict() -> ConflictFinding:
    return ConflictFinding(
        kind=ConflictKind.PHENOTYPE_DISAGREEMENT,
        severity=ConflictSeverity.HARD,
        reason="CYP2C19 *2/*2 disagreed on phenotype",
        source_ids=("PMID:1", "PMID:2"),
        key=("CYP2C19", "*2/*2", "SAS"),
    )


def _provenance_report(complete: bool) -> ProvenanceCoverageReport:
    """Build a ProvenanceCoverageReport that is either all-COVERED or
    all-MISSING.

    Used to exercise R4 — when complete=False, the report's
    ``is_complete`` is False, triggering ABSTAIN."""
    states = {
        d: DimensionState.COVERED if complete else DimensionState.MISSING for d in ALL_DIMENSIONS
    }
    offenders = {d: () for d in ALL_DIMENSIONS}
    reasons = {d: "test" for d in ALL_DIMENSIONS}
    return ProvenanceCoverageReport(
        correlation_id="test",
        total_records=1,
        dimension_states=MappingProxyType(states),
        offenders=MappingProxyType(offenders),
        reasons=MappingProxyType(reasons),
    )


@pytest.fixture
def engine() -> SufficiencyDecisionEngine:
    return SufficiencyDecisionEngine()


# ---------------------------------------------------------------------------
# Closed enum contract
# ---------------------------------------------------------------------------


class TestSufficiencyDecisionEnum:
    def test_enum_has_exactly_7_decisions(self) -> None:
        assert len(list(SufficiencyDecision)) == 7

    def test_decision_values_are_stable(self) -> None:
        # Wire format — downstream UI / JSON consumers read these.
        assert SufficiencyDecision.SUFFICIENT.value == "sufficient"
        assert SufficiencyDecision.BLOCK.value == "block"
        assert SufficiencyDecision.ABSTAIN.value == "abstain"
        assert SufficiencyDecision.DOWNGRADE.value == "downgrade"
        assert SufficiencyDecision.ESCALATE.value == "escalate"
        assert SufficiencyDecision.REQUEST_MORE.value == "request_more"
        assert SufficiencyDecision.PASS_WITH_CAVEAT.value == "pass_with_caveat"


# ---------------------------------------------------------------------------
# R1 — hard conflict or CONFLICT_FREE MISSING -> BLOCK
# ---------------------------------------------------------------------------


class TestR1HardConflict:
    def test_hard_finding_blocks(self, engine: SufficiencyDecisionEngine, covered_analysis) -> None:
        report = engine.decide(
            covered_analysis,
            findings=[_hard_phenotype_conflict()],
        )
        assert report.decision is SufficiencyDecision.BLOCK
        assert report.rationale.startswith("R1")

    def test_conflict_free_missing_blocks(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={ClaimEvidenceFacet.CONFLICT_FREE: FacetCoverageState.MISSING},
        )
        report = engine.decide(analysis)
        assert report.decision is SufficiencyDecision.BLOCK
        assert report.rationale.startswith("R1")


# ---------------------------------------------------------------------------
# R2 — PHENOTYPE MISSING -> BLOCK
# ---------------------------------------------------------------------------


class TestR2PhenotypeMissing:
    def test_phenotype_missing_blocks(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={ClaimEvidenceFacet.PHENOTYPE: FacetCoverageState.MISSING},
        )
        report = engine.decide(analysis)
        assert report.decision is SufficiencyDecision.BLOCK
        assert report.rationale.startswith("R2")


# ---------------------------------------------------------------------------
# R3 — RECOMMENDATION MISSING -> BLOCK
# ---------------------------------------------------------------------------


class TestR3RecommendationMissing:
    def test_recommendation_missing_blocks(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.RECOMMENDATION: FacetCoverageState.MISSING,
            },
        )
        report = engine.decide(analysis)
        assert report.decision is SufficiencyDecision.BLOCK
        assert report.rationale.startswith("R3")


# ---------------------------------------------------------------------------
# R4 — provenance incomplete -> ABSTAIN
# ---------------------------------------------------------------------------


class TestR4ProvenanceIncomplete:
    def test_incomplete_provenance_abstains(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        report = engine.decide(
            covered_analysis,
            provenance=_provenance_report(complete=False),
        )
        assert report.decision is SufficiencyDecision.ABSTAIN
        assert report.rationale.startswith("R4")

    def test_complete_provenance_does_not_abstain(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        report = engine.decide(
            covered_analysis,
            provenance=_provenance_report(complete=True),
        )
        assert report.decision is SufficiencyDecision.SUFFICIENT

    def test_no_provenance_supplied_does_not_abstain(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        """When the caller passes no provenance report, R4 must not
        fire — the engine can't know it's incomplete."""
        report = engine.decide(covered_analysis)
        assert report.decision is SufficiencyDecision.SUFFICIENT


# ---------------------------------------------------------------------------
# R5 — POPULATION MISSING -> ESCALATE
# ---------------------------------------------------------------------------


class TestR5PopulationMissing:
    def test_population_missing_escalates(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={ClaimEvidenceFacet.POPULATION: FacetCoverageState.MISSING},
        )
        report = engine.decide(analysis)
        assert report.decision is SufficiencyDecision.ESCALATE
        assert report.rationale.startswith("R5")


# ---------------------------------------------------------------------------
# R6 — CPIC MISSING -> REQUEST_MORE
# ---------------------------------------------------------------------------


class TestR6CpicMissing:
    def test_cpic_missing_requests_more(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={ClaimEvidenceFacet.CPIC: FacetCoverageState.MISSING},
        )
        report = engine.decide(analysis)
        assert report.decision is SufficiencyDecision.REQUEST_MORE
        assert report.rationale.startswith("R6")


# ---------------------------------------------------------------------------
# R7 — ALLELE MISSING -> REQUEST_MORE
# ---------------------------------------------------------------------------


class TestR7AlleleMissing:
    def test_allele_missing_requests_more(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={ClaimEvidenceFacet.ALLELE: FacetCoverageState.MISSING},
        )
        report = engine.decide(analysis)
        assert report.decision is SufficiencyDecision.REQUEST_MORE
        assert report.rationale.startswith("R7")


# ---------------------------------------------------------------------------
# R8 — RECOMMENDATION UNCERTAIN -> DOWNGRADE
# ---------------------------------------------------------------------------


class TestR8RecommendationUncertain:
    def test_recommendation_uncertain_downgrades(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.RECOMMENDATION: FacetCoverageState.UNCERTAIN,
            },
        )
        report = engine.decide(analysis)
        assert report.decision is SufficiencyDecision.DOWNGRADE
        assert report.rationale.startswith("R8")


# ---------------------------------------------------------------------------
# R9 — POPULATION UNCERTAIN -> DOWNGRADE
# ---------------------------------------------------------------------------


class TestR9PopulationUncertain:
    def test_population_uncertain_downgrades(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.POPULATION: FacetCoverageState.UNCERTAIN,
            },
        )
        report = engine.decide(analysis)
        assert report.decision is SufficiencyDecision.DOWNGRADE
        assert report.rationale.startswith("R9")


# ---------------------------------------------------------------------------
# R10 — any other UNCERTAIN (ALLELE / CPIC / PHENOTYPE) -> DOWNGRADE
# ---------------------------------------------------------------------------


class TestR10OtherUncertain:
    @pytest.mark.parametrize(
        "facet",
        [
            ClaimEvidenceFacet.ALLELE,
            ClaimEvidenceFacet.CPIC,
            ClaimEvidenceFacet.PHENOTYPE,
        ],
    )
    def test_other_uncertain_facet_downgrades(
        self,
        engine: SufficiencyDecisionEngine,
        covered_analysis,
        facet: ClaimEvidenceFacet,
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={facet: FacetCoverageState.UNCERTAIN},
        )
        report = engine.decide(analysis)
        assert report.decision is SufficiencyDecision.DOWNGRADE
        assert report.rationale.startswith("R10")


# ---------------------------------------------------------------------------
# R11 — ONLY CONFLICT_FREE UNCERTAIN (soft conflict) -> PASS_WITH_CAVEAT
# ---------------------------------------------------------------------------


class TestR11SoftConflictOnly:
    def test_only_conflict_free_uncertain_passes_with_caveat(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.CONFLICT_FREE: FacetCoverageState.UNCERTAIN,
            },
        )
        report = engine.decide(analysis)
        assert report.decision is SufficiencyDecision.PASS_WITH_CAVEAT
        assert report.rationale.startswith("R11")


# ---------------------------------------------------------------------------
# R12 — all COVERED, no conflict -> SUFFICIENT
# ---------------------------------------------------------------------------


class TestR12Sufficient:
    def test_all_covered_is_sufficient(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        report = engine.decide(covered_analysis)
        assert report.decision is SufficiencyDecision.SUFFICIENT
        assert report.rationale.startswith("R12")


# ---------------------------------------------------------------------------
# Priority ordering — higher-priority rules must always win
# ---------------------------------------------------------------------------


class TestPriorityOrdering:
    def test_r1_beats_r2_when_both_would_apply(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        # Both phenotype missing AND hard conflict -> R1 (BLOCK) fires
        # first even though R2 would also BLOCK.
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.PHENOTYPE: FacetCoverageState.MISSING,
            },
        )
        report = engine.decide(analysis, findings=[_hard_phenotype_conflict()])
        assert report.decision is SufficiencyDecision.BLOCK
        assert report.rationale.startswith("R1")

    def test_r3_fires_before_r5_when_both_missing(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.RECOMMENDATION: FacetCoverageState.MISSING,
                ClaimEvidenceFacet.POPULATION: FacetCoverageState.MISSING,
            },
        )
        report = engine.decide(analysis)
        # R3 (BLOCK) beats R5 (ESCALATE) by priority.
        assert report.decision is SufficiencyDecision.BLOCK
        assert report.rationale.startswith("R3")

    def test_r8_fires_before_r9_when_both_uncertain(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.RECOMMENDATION: FacetCoverageState.UNCERTAIN,
                ClaimEvidenceFacet.POPULATION: FacetCoverageState.UNCERTAIN,
            },
        )
        report = engine.decide(analysis)
        assert report.decision is SufficiencyDecision.DOWNGRADE
        assert report.rationale.startswith("R8")


# ---------------------------------------------------------------------------
# Report properties and serialization
# ---------------------------------------------------------------------------


class TestReportProperties:
    def test_is_blocking_for_block_and_abstain(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        # BLOCK via R1.
        r1 = engine.decide(covered_analysis, findings=[_hard_phenotype_conflict()])
        assert r1.is_blocking
        assert not r1.allows_synthesis

        # ABSTAIN via R4.
        r4 = engine.decide(covered_analysis, provenance=_provenance_report(complete=False))
        assert r4.is_blocking
        assert not r4.allows_synthesis

    def test_allows_synthesis_for_sufficient_downgrade_and_caveat(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        r12 = engine.decide(covered_analysis)
        assert r12.allows_synthesis
        assert not r12.is_blocking

        r8 = engine.decide(
            make_analysis_with_state(
                base=covered_analysis,
                overrides={
                    ClaimEvidenceFacet.RECOMMENDATION: FacetCoverageState.UNCERTAIN,
                },
            )
        )
        assert r8.allows_synthesis  # DOWNGRADE still synthesises

    def test_to_dict_is_jsonable(self, engine: SufficiencyDecisionEngine, covered_analysis) -> None:
        import json

        r = engine.decide(covered_analysis)
        # Must round-trip through JSON — downstream UI expects this shape.
        dumped = json.dumps(r.to_dict())
        # Re-parse and sanity-check the top-level shape.
        payload = json.loads(dumped)
        assert payload["decision"] == "sufficient"
        assert "rationale" in payload
        assert "coverage" in payload
        assert "allows_synthesis" in payload

    def test_correlation_id_propagates_from_coverage(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        assert covered_analysis.correlation_id == "test-correlation"
        r = engine.decide(covered_analysis)
        assert r.correlation_id == "test-correlation"


# ---------------------------------------------------------------------------
# Determinism — same input, same output
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_repeated_calls_produce_same_decision(
        self, engine: SufficiencyDecisionEngine, covered_analysis
    ) -> None:
        r1 = engine.decide(covered_analysis)
        r2 = engine.decide(covered_analysis)
        r3 = engine.decide(covered_analysis)
        assert r1.decision is r2.decision is r3.decision
        assert r1.rationale == r2.rationale == r3.rationale
