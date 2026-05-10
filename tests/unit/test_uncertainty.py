"""Tests for ``core.evidence_sufficiency.uncertainty``.

Covers the full 9-rule scoring table plus the tier-to-action mapping
and the ``UncertaintyAwareReasoningLayer`` policy wrapper.

Scoring rule table (from the module docstring):

    U1  any HARD conflict finding                     -> UNSAFE
    U2  any MISSING facet (non-CONFLICT_FREE)         -> HIGH
    U3  POPULATION facet UNCERTAIN                    -> HIGH
    U4  KG path bundle supplied AND empty             -> HIGH
    U5  >=2 uncertain facets total                    -> HIGH
    U6  CONFLICT_FREE UNCERTAIN (soft conflict)       -> MODERATE
    U7  exactly 1 uncertain non-core facet (ALLELE or CPIC) -> MODERATE
    U8  KG path bundle supplied AND only 1 path       -> MODERATE
    U9  otherwise                                     -> LOW

Tier -> action mapping (closed; code change to alter):

    LOW       PROCEED
    MODERATE  PROCEED
    HIGH      REQUEST_MORE
    UNSAFE    BLOCK
"""

from __future__ import annotations

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
from core.evidence_sufficiency.uncertainty.engine import (
    UncertaintyAction,
    UncertaintyAwareReasoningLayer,
    UncertaintyReading,
    UncertaintyScore,
    UncertaintyScoringEngine,
)

from tests.conftest import make_analysis_with_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hard_conflict() -> ConflictFinding:
    return ConflictFinding(
        kind=ConflictKind.PHENOTYPE_DISAGREEMENT,
        severity=ConflictSeverity.HARD,
        reason="hard conflict",
        source_ids=("PMID:1", "PMID:2"),
        key=("CYP2C19", "*2/*2", "SAS"),
    )


def _soft_conflict() -> ConflictFinding:
    return ConflictFinding(
        kind=ConflictKind.POPULATION_DIVERGENCE,
        severity=ConflictSeverity.SOFT,
        reason="soft divergence",
        source_ids=("PMID:a", "PMID:b"),
        key=("CYP2C19*2", "SAS"),
    )


@pytest.fixture
def engine() -> UncertaintyScoringEngine:
    return UncertaintyScoringEngine()


@pytest.fixture
def layer() -> UncertaintyAwareReasoningLayer:
    return UncertaintyAwareReasoningLayer()


# ---------------------------------------------------------------------------
# Closed enum contracts
# ---------------------------------------------------------------------------


class TestUncertaintyScoreEnum:
    def test_has_exactly_4_tiers(self) -> None:
        assert len(list(UncertaintyScore)) == 4

    def test_tier_values_are_stable(self) -> None:
        assert UncertaintyScore.LOW.value == "low"
        assert UncertaintyScore.MODERATE.value == "moderate"
        assert UncertaintyScore.HIGH.value == "high"
        assert UncertaintyScore.UNSAFE.value == "unsafe"


class TestUncertaintyActionEnum:
    def test_has_exactly_5_actions(self) -> None:
        assert len(list(UncertaintyAction)) == 5

    def test_action_values_are_stable(self) -> None:
        assert UncertaintyAction.PROCEED.value == "proceed"
        assert UncertaintyAction.REQUEST_MORE.value == "request_more"
        assert UncertaintyAction.ABSTAIN.value == "abstain"
        assert UncertaintyAction.ESCALATE.value == "escalate"
        assert UncertaintyAction.BLOCK.value == "block"


# ---------------------------------------------------------------------------
# U1 — hard conflict -> UNSAFE
# ---------------------------------------------------------------------------


class TestU1HardConflict:
    def test_hard_conflict_is_unsafe(
        self, engine: UncertaintyScoringEngine, covered_analysis
    ) -> None:
        reading = engine.score(covered_analysis, findings=[_hard_conflict()])
        assert reading.score is UncertaintyScore.UNSAFE
        assert reading.rule_id == "U1"
        assert reading.action is UncertaintyAction.BLOCK


# ---------------------------------------------------------------------------
# U2 — missing non-CONFLICT_FREE facet -> HIGH
# ---------------------------------------------------------------------------


class TestU2MissingFacet:
    @pytest.mark.parametrize(
        "facet",
        [
            ClaimEvidenceFacet.ALLELE,
            ClaimEvidenceFacet.PHENOTYPE,
            ClaimEvidenceFacet.CPIC,
            ClaimEvidenceFacet.POPULATION,
            ClaimEvidenceFacet.RECOMMENDATION,
        ],
    )
    def test_missing_non_conflict_facet_is_high(
        self,
        engine: UncertaintyScoringEngine,
        covered_analysis,
        facet: ClaimEvidenceFacet,
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={facet: FacetCoverageState.MISSING},
        )
        reading = engine.score(analysis)
        assert reading.score is UncertaintyScore.HIGH
        assert reading.rule_id == "U2"
        assert reading.action is UncertaintyAction.REQUEST_MORE


# ---------------------------------------------------------------------------
# U3 — POPULATION uncertain -> HIGH
# ---------------------------------------------------------------------------


class TestU3PopulationUncertain:
    def test_population_uncertain_is_high(
        self, engine: UncertaintyScoringEngine, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.POPULATION: FacetCoverageState.UNCERTAIN,
            },
        )
        reading = engine.score(analysis)
        assert reading.score is UncertaintyScore.HIGH
        assert reading.rule_id == "U3"


# ---------------------------------------------------------------------------
# U4 — empty path bundle -> HIGH
# ---------------------------------------------------------------------------


class TestU4EmptyPathBundle:
    def test_empty_bundle_is_high(self, engine: UncertaintyScoringEngine, covered_analysis) -> None:
        reading = engine.score(covered_analysis, path_bundle=())
        assert reading.score is UncertaintyScore.HIGH
        assert reading.rule_id == "U4"

    def test_none_bundle_does_not_fire_u4(
        self, engine: UncertaintyScoringEngine, covered_analysis
    ) -> None:
        reading = engine.score(covered_analysis, path_bundle=None)
        assert reading.score is UncertaintyScore.LOW
        assert reading.rule_id == "U9"


# ---------------------------------------------------------------------------
# U5 — 2+ uncertain facets -> HIGH
# ---------------------------------------------------------------------------


class TestU5MultipleUncertain:
    def test_two_non_core_uncertain_is_high(
        self, engine: UncertaintyScoringEngine, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.ALLELE: FacetCoverageState.UNCERTAIN,
                ClaimEvidenceFacet.CPIC: FacetCoverageState.UNCERTAIN,
            },
        )
        reading = engine.score(analysis)
        assert reading.score is UncertaintyScore.HIGH
        assert reading.rule_id == "U5"


# ---------------------------------------------------------------------------
# U6 — CONFLICT_FREE UNCERTAIN (soft conflict) -> MODERATE
# ---------------------------------------------------------------------------


class TestU6SoftConflictOnly:
    def test_soft_conflict_only_is_moderate(
        self, engine: UncertaintyScoringEngine, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.CONFLICT_FREE: FacetCoverageState.UNCERTAIN,
            },
        )
        reading = engine.score(analysis, findings=[_soft_conflict()])
        assert reading.score is UncertaintyScore.MODERATE
        assert reading.rule_id == "U6"
        assert reading.action is UncertaintyAction.PROCEED


# ---------------------------------------------------------------------------
# U7 — exactly 1 non-core uncertain (ALLELE or CPIC) -> MODERATE
# ---------------------------------------------------------------------------


class TestU7SingleNonCoreUncertain:
    @pytest.mark.parametrize(
        "facet",
        [ClaimEvidenceFacet.ALLELE, ClaimEvidenceFacet.CPIC],
    )
    def test_exactly_one_non_core_uncertain_is_moderate(
        self,
        engine: UncertaintyScoringEngine,
        covered_analysis,
        facet: ClaimEvidenceFacet,
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={facet: FacetCoverageState.UNCERTAIN},
        )
        reading = engine.score(analysis)
        assert reading.score is UncertaintyScore.MODERATE
        assert reading.rule_id == "U7"


# ---------------------------------------------------------------------------
# U8 — single KG path -> MODERATE
# ---------------------------------------------------------------------------


class TestU8ThinPathway:
    def test_single_path_is_moderate(
        self, engine: UncertaintyScoringEngine, covered_analysis
    ) -> None:
        reading = engine.score(covered_analysis, path_bundle=("only_path",))
        assert reading.score is UncertaintyScore.MODERATE
        assert reading.rule_id == "U8"

    def test_two_paths_fall_through_to_low(
        self, engine: UncertaintyScoringEngine, covered_analysis
    ) -> None:
        reading = engine.score(covered_analysis, path_bundle=("p1", "p2"))
        assert reading.score is UncertaintyScore.LOW
        assert reading.rule_id == "U9"


# ---------------------------------------------------------------------------
# U9 — otherwise -> LOW
# ---------------------------------------------------------------------------


class TestU9Low:
    def test_all_clean_no_bundle_is_low(
        self, engine: UncertaintyScoringEngine, covered_analysis
    ) -> None:
        reading = engine.score(covered_analysis)
        assert reading.score is UncertaintyScore.LOW
        assert reading.rule_id == "U9"
        assert reading.action is UncertaintyAction.PROCEED

    def test_all_clean_with_two_paths_is_low(
        self, engine: UncertaintyScoringEngine, covered_analysis
    ) -> None:
        reading = engine.score(covered_analysis, path_bundle=("a", "b", "c"))
        assert reading.score is UncertaintyScore.LOW


# ---------------------------------------------------------------------------
# Tier -> action mapping
# ---------------------------------------------------------------------------


class TestTierActionMapping:
    """The closed tier→action map is the contract downstream policy
    reads. Locking these pairs prevents silent policy drift."""

    def test_low_proceeds(self, engine: UncertaintyScoringEngine, covered_analysis) -> None:
        r = engine.score(covered_analysis)
        assert r.score is UncertaintyScore.LOW
        assert r.action is UncertaintyAction.PROCEED

    def test_moderate_proceeds(self, engine: UncertaintyScoringEngine, covered_analysis) -> None:
        r = engine.score(covered_analysis, path_bundle=("one",))
        assert r.score is UncertaintyScore.MODERATE
        assert r.action is UncertaintyAction.PROCEED

    def test_high_requests_more(self, engine: UncertaintyScoringEngine, covered_analysis) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.POPULATION: FacetCoverageState.UNCERTAIN,
            },
        )
        r = engine.score(analysis)
        assert r.score is UncertaintyScore.HIGH
        assert r.action is UncertaintyAction.REQUEST_MORE

    def test_unsafe_blocks(self, engine: UncertaintyScoringEngine, covered_analysis) -> None:
        r = engine.score(covered_analysis, findings=[_hard_conflict()])
        assert r.score is UncertaintyScore.UNSAFE
        assert r.action is UncertaintyAction.BLOCK


# ---------------------------------------------------------------------------
# UncertaintyAwareReasoningLayer
# ---------------------------------------------------------------------------


class TestReasoningLayer:
    def test_layer_decide_delegates_to_engine(
        self,
        layer: UncertaintyAwareReasoningLayer,
        covered_analysis,
    ) -> None:
        reading = layer.decide(covered_analysis)
        assert isinstance(reading, UncertaintyReading)
        assert reading.score is UncertaintyScore.LOW

    def test_recommended_action_re_derives_from_reading(
        self,
        layer: UncertaintyAwareReasoningLayer,
        engine: UncertaintyScoringEngine,
        covered_analysis,
    ) -> None:
        # Produce an unsafe reading via the engine, confirm the static
        # helper re-derives BLOCK.
        unsafe = engine.score(covered_analysis, findings=[_hard_conflict()])
        assert layer.recommended_action(unsafe) is UncertaintyAction.BLOCK


# ---------------------------------------------------------------------------
# Determinism + JSON roundtrip
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_input_same_output(
        self, engine: UncertaintyScoringEngine, covered_analysis
    ) -> None:
        r1 = engine.score(covered_analysis)
        r2 = engine.score(covered_analysis)
        assert r1.score is r2.score
        assert r1.rule_id == r2.rule_id
        assert r1.rationale == r2.rationale


class TestJsonRoundtrip:
    def test_reading_is_jsonable(self, engine: UncertaintyScoringEngine, covered_analysis) -> None:
        import json

        r = engine.score(covered_analysis, findings=[_soft_conflict()])
        dumped = json.loads(json.dumps(r.to_dict()))
        assert dumped["score"] in {"low", "moderate", "high", "unsafe"}
        assert dumped["action"] in {"proceed", "request_more", "abstain", "escalate", "block"}
        assert "rule_id" in dumped
        assert "rationale" in dumped
        assert "coverage_ratio" in dumped
