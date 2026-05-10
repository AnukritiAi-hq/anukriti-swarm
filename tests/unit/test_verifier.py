"""Tests for ``core.evidence_sufficiency.verifier.set_level``.

Exhaustive coverage of the 10-rule V-table. Rules fire in priority
order V1..V10 and the first match wins, so each test constructs the
minimal coverage shape that isolates one rule.

V-table contract (from the module docstring):

    V1  hard RECOMMENDATION_CLASH with a named invertor
        (USE vs AVOID/CONTRAINDICATED)               -> REFUTED
    V2  any other HARD conflict                      -> CONFLICTING
    V3  PHENOTYPE MISSING                            -> INSUFFICIENT
    V4  RECOMMENDATION MISSING                       -> INSUFFICIENT
    V5  any other MISSING facet (ALLELE/CPIC/POPULATION) -> INSUFFICIENT
    V6  KG path bundle supplied AND empty            -> UNCERTAIN
    V7  POPULATION UNCERTAIN                         -> UNCERTAIN
    V8  any other UNCERTAIN facet                    -> UNCERTAIN
    V9  CONFLICT_FREE UNCERTAIN (soft conflict only) -> UNCERTAIN
    V10 all COVERED, no HARD conflict                -> SUPPORTED
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
from core.evidence_sufficiency.verifier.result import EvidenceVerdict
from core.evidence_sufficiency.verifier.set_level import SetLevelEvidenceVerifier

from tests.conftest import make_analysis_with_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hard_rec_clash(actions_text: str) -> ConflictFinding:
    """Build a HARD RECOMMENDATION_CLASH. ``actions_text`` becomes the
    reason-string tail (after the colon). V1 detection re-parses this."""
    return ConflictFinding(
        kind=ConflictKind.RECOMMENDATION_CLASH,
        severity=ConflictSeverity.HARD,
        reason=f"clopidogrel for CYP2C19/pm: {actions_text}",
        source_ids=("PMID:a", "PMID:b"),
        key=("clopidogrel", "CYP2C19", "pm"),
    )


def _hard_phenotype_conflict() -> ConflictFinding:
    return ConflictFinding(
        kind=ConflictKind.PHENOTYPE_DISAGREEMENT,
        severity=ConflictSeverity.HARD,
        reason="sources disagree on phenotype",
        source_ids=("PMID:1", "PMID:2"),
        key=("CYP2C19", "*2/*2", "SAS"),
    )


def _soft_population_conflict() -> ConflictFinding:
    return ConflictFinding(
        kind=ConflictKind.POPULATION_DIVERGENCE,
        severity=ConflictSeverity.SOFT,
        reason="CYP2C19*2 freq 0.36 vs 0.12",
        source_ids=("PMID:freq1", "PMID:freq2"),
        key=("CYP2C19*2", "SAS"),
    )


@pytest.fixture
def verifier() -> SetLevelEvidenceVerifier:
    return SetLevelEvidenceVerifier()


# ---------------------------------------------------------------------------
# Closed-enum contract
# ---------------------------------------------------------------------------


class TestEvidenceVerdictEnum:
    def test_has_exactly_5_verdicts(self) -> None:
        assert len(list(EvidenceVerdict)) == 5

    def test_verdict_values_are_stable(self) -> None:
        assert EvidenceVerdict.SUPPORTED.value == "supported"
        assert EvidenceVerdict.REFUTED.value == "refuted"
        assert EvidenceVerdict.INSUFFICIENT.value == "insufficient"
        assert EvidenceVerdict.CONFLICTING.value == "conflicting"
        assert EvidenceVerdict.UNCERTAIN.value == "uncertain"


# ---------------------------------------------------------------------------
# V1 — named invertor (USE vs AVOID) -> REFUTED
# ---------------------------------------------------------------------------


class TestV1NamedInvertor:
    def test_use_vs_avoid_is_refuted(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        result = verifier.verify(
            covered_analysis,
            findings=[_hard_rec_clash("use vs avoid")],
        )
        assert result.verdict is EvidenceVerdict.REFUTED
        assert result.rule_id == "V1"

    def test_use_vs_contraindicated_is_refuted(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        result = verifier.verify(
            covered_analysis,
            findings=[_hard_rec_clash("use vs contraindicated")],
        )
        assert result.verdict is EvidenceVerdict.REFUTED
        assert result.rule_id == "V1"


# ---------------------------------------------------------------------------
# V2 — other hard conflict -> CONFLICTING
# ---------------------------------------------------------------------------


class TestV2OtherHardConflict:
    def test_phenotype_disagreement_is_conflicting(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        result = verifier.verify(
            covered_analysis,
            findings=[_hard_phenotype_conflict()],
        )
        assert result.verdict is EvidenceVerdict.CONFLICTING
        assert result.rule_id == "V2"

    def test_unnamed_recommendation_clash_is_conflicting(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        """Clash where neither side is classified as USE falls through
        V1 to V2."""
        # 'avoid vs contraindicated' — both restrictive, no USE invertor.
        result = verifier.verify(
            covered_analysis,
            findings=[_hard_rec_clash("avoid vs contraindicated")],
        )
        # Should be CONFLICTING (V2), not REFUTED (V1).
        assert result.verdict is EvidenceVerdict.CONFLICTING
        assert result.rule_id == "V2"


# ---------------------------------------------------------------------------
# V3 — PHENOTYPE MISSING -> INSUFFICIENT
# ---------------------------------------------------------------------------


class TestV3PhenotypeMissing:
    def test_phenotype_missing_is_insufficient(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={ClaimEvidenceFacet.PHENOTYPE: FacetCoverageState.MISSING},
        )
        result = verifier.verify(analysis)
        assert result.verdict is EvidenceVerdict.INSUFFICIENT
        assert result.rule_id == "V3"


# ---------------------------------------------------------------------------
# V4 — RECOMMENDATION MISSING -> INSUFFICIENT
# ---------------------------------------------------------------------------


class TestV4RecommendationMissing:
    def test_recommendation_missing_is_insufficient(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.RECOMMENDATION: FacetCoverageState.MISSING,
            },
        )
        result = verifier.verify(analysis)
        assert result.verdict is EvidenceVerdict.INSUFFICIENT
        assert result.rule_id == "V4"


# ---------------------------------------------------------------------------
# V5 — other MISSING facets -> INSUFFICIENT
# ---------------------------------------------------------------------------


class TestV5OtherMissing:
    @pytest.mark.parametrize(
        "facet",
        [
            ClaimEvidenceFacet.ALLELE,
            ClaimEvidenceFacet.CPIC,
            ClaimEvidenceFacet.POPULATION,
        ],
    )
    def test_non_core_missing_is_v5_insufficient(
        self,
        verifier: SetLevelEvidenceVerifier,
        covered_analysis,
        facet: ClaimEvidenceFacet,
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={facet: FacetCoverageState.MISSING},
        )
        result = verifier.verify(analysis)
        assert result.verdict is EvidenceVerdict.INSUFFICIENT
        assert result.rule_id == "V5"


# ---------------------------------------------------------------------------
# V6 — pathway bundle supplied but empty -> UNCERTAIN
# ---------------------------------------------------------------------------


class TestV6EmptyPathBundle:
    def test_empty_bundle_is_uncertain(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        # Explicit empty tuple — caller *asked* for pathway, got nothing.
        result = verifier.verify(covered_analysis, path_bundle=())
        assert result.verdict is EvidenceVerdict.UNCERTAIN
        assert result.rule_id == "V6"

    def test_none_bundle_does_not_fire_v6(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        # No bundle passed -> pathway is simply not part of the decision.
        # Should fall through to V10 SUPPORTED on fully-covered analysis.
        result = verifier.verify(covered_analysis, path_bundle=None)
        assert result.verdict is EvidenceVerdict.SUPPORTED
        assert result.rule_id == "V10"


# ---------------------------------------------------------------------------
# V7 — POPULATION UNCERTAIN -> UNCERTAIN
# ---------------------------------------------------------------------------


class TestV7PopulationUncertain:
    def test_population_uncertain_is_v7(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.POPULATION: FacetCoverageState.UNCERTAIN,
            },
        )
        result = verifier.verify(analysis)
        assert result.verdict is EvidenceVerdict.UNCERTAIN
        assert result.rule_id == "V7"


# ---------------------------------------------------------------------------
# V8 — other UNCERTAIN facets -> UNCERTAIN
# ---------------------------------------------------------------------------


class TestV8OtherUncertain:
    @pytest.mark.parametrize(
        "facet",
        [
            ClaimEvidenceFacet.ALLELE,
            ClaimEvidenceFacet.CPIC,
            ClaimEvidenceFacet.PHENOTYPE,
            ClaimEvidenceFacet.RECOMMENDATION,
        ],
    )
    def test_non_population_non_conflict_uncertain_is_v8(
        self,
        verifier: SetLevelEvidenceVerifier,
        covered_analysis,
        facet: ClaimEvidenceFacet,
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={facet: FacetCoverageState.UNCERTAIN},
        )
        result = verifier.verify(analysis)
        assert result.verdict is EvidenceVerdict.UNCERTAIN
        assert result.rule_id == "V8"


# ---------------------------------------------------------------------------
# V9 — only CONFLICT_FREE uncertain (soft conflict) -> UNCERTAIN
# ---------------------------------------------------------------------------


class TestV9SoftConflictOnly:
    def test_soft_conflict_only_is_v9(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.CONFLICT_FREE: FacetCoverageState.UNCERTAIN,
            },
        )
        result = verifier.verify(analysis, findings=[_soft_population_conflict()])
        assert result.verdict is EvidenceVerdict.UNCERTAIN
        assert result.rule_id == "V9"


# ---------------------------------------------------------------------------
# V10 — all COVERED, no hard conflict -> SUPPORTED
# ---------------------------------------------------------------------------


class TestV10Supported:
    def test_all_covered_is_supported(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        result = verifier.verify(covered_analysis)
        assert result.verdict is EvidenceVerdict.SUPPORTED
        assert result.rule_id == "V10"

    def test_with_non_empty_path_bundle_is_supported(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        # Non-empty bundle doesn't cause a downgrade — V10 fires as long
        # as everything is clean.
        result = verifier.verify(
            covered_analysis,
            path_bundle=("fake_path_1", "fake_path_2"),  # opaque; verifier only reads len()
        )
        assert result.verdict is EvidenceVerdict.SUPPORTED
        assert result.rule_id == "V10"
        assert result.pathway_complete
        assert result.pathway_count == 2


# ---------------------------------------------------------------------------
# Priority — higher rules beat lower
# ---------------------------------------------------------------------------


class TestPriorityOrdering:
    def test_v1_beats_v2_on_same_finding(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        """When there's a USE/AVOID clash AND a phenotype disagreement,
        V1 (REFUTED) fires first — we can name the refuting signal."""
        result = verifier.verify(
            covered_analysis,
            findings=[
                _hard_rec_clash("use vs avoid"),
                _hard_phenotype_conflict(),
            ],
        )
        assert result.verdict is EvidenceVerdict.REFUTED
        assert result.rule_id == "V1"

    def test_v3_beats_v5_when_phenotype_and_allele_missing(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.PHENOTYPE: FacetCoverageState.MISSING,
                ClaimEvidenceFacet.ALLELE: FacetCoverageState.MISSING,
            },
        )
        result = verifier.verify(analysis)
        assert result.verdict is EvidenceVerdict.INSUFFICIENT
        assert result.rule_id == "V3"

    def test_v6_beats_v7_when_both_conditions_present(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        # Population uncertain AND empty path bundle supplied -> V6 wins.
        analysis = make_analysis_with_state(
            base=covered_analysis,
            overrides={
                ClaimEvidenceFacet.POPULATION: FacetCoverageState.UNCERTAIN,
            },
        )
        result = verifier.verify(analysis, path_bundle=())
        assert result.rule_id == "V6"


# ---------------------------------------------------------------------------
# allows_synthesis only True when SUPPORTED
# ---------------------------------------------------------------------------


class TestAllowsSynthesis:
    def test_supported_allows_synthesis(
        self, verifier: SetLevelEvidenceVerifier, covered_analysis
    ) -> None:
        assert verifier.verify(covered_analysis).allows_synthesis

    @pytest.mark.parametrize(
        "findings, overrides",
        [
            ([_hard_rec_clash("use vs avoid")], {}),  # REFUTED
            ([_hard_phenotype_conflict()], {}),  # CONFLICTING
            ([], {ClaimEvidenceFacet.PHENOTYPE: FacetCoverageState.MISSING}),  # INSUFFICIENT
            ([], {ClaimEvidenceFacet.POPULATION: FacetCoverageState.UNCERTAIN}),  # UNCERTAIN
        ],
    )
    def test_non_supported_blocks_synthesis(
        self,
        verifier: SetLevelEvidenceVerifier,
        covered_analysis,
        findings,
        overrides,
    ) -> None:
        analysis = (
            make_analysis_with_state(base=covered_analysis, overrides=overrides)
            if overrides
            else covered_analysis
        )
        result = verifier.verify(analysis, findings=findings)
        assert not result.allows_synthesis


# ---------------------------------------------------------------------------
# to_dict JSON roundtrip
# ---------------------------------------------------------------------------


class TestJsonRoundtrip:
    def test_result_is_jsonable(self, verifier: SetLevelEvidenceVerifier, covered_analysis) -> None:
        import json

        result = verifier.verify(covered_analysis)
        dumped = json.loads(json.dumps(result.to_dict()))
        assert dumped["verdict"] == "supported"
        assert dumped["rule_id"] == "V10"
        assert dumped["allows_synthesis"] is True
