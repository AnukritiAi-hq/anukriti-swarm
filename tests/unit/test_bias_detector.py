"""Tests for ``core.evidence_sufficiency.uncertainty.bias_detector``.

Three closed bias kinds (extending is a code change):

    EUROCENTRIC_IMBALANCE       target is non-EUR + target evidence=0
                                + EUR evidence>0
    ANCESTRY_SCARCITY           target allele count / max < threshold
    UNSUPPORTED_EXTRAPOLATION   POPULATION UNCERTAIN + 0 target KG
                                frequency data

Tests exercise each rule in isolation and the threshold edge cases
(scarcity_ratio, min_target_evidence).
"""

from __future__ import annotations

import pytest
from core.evidence_sufficiency.coverage.claim_coverage import (
    ClaimCoverageAnalysis,
    ClaimEvidenceFacet,
    FacetCoverageState,
)
from core.evidence_sufficiency.uncertainty.bias_detector import (
    BiasKind,
    PopulationEvidenceBiasDetector,
)
from core.models.population import SuperPopulation

from tests.conftest import (
    FLAGSHIP_DRUG,
    FLAGSHIP_GENE,
    FLAGSHIP_GENOTYPE,
    make_pop_indexer,
)

# ---------------------------------------------------------------------------
# Helpers — build analyses for specific target populations
# ---------------------------------------------------------------------------


def _analysis_for(
    population: SuperPopulation,
    *,
    pop_state: FacetCoverageState = FacetCoverageState.COVERED,
) -> ClaimCoverageAnalysis:
    """All-COVERED analysis on a specific population, optionally
    downgrading the POPULATION facet to UNCERTAIN for rule 3 tests."""
    from core.evidence_sufficiency.coverage.claim_coverage import ALL_FACETS

    base = ClaimCoverageAnalysis.empty(
        drug=FLAGSHIP_DRUG,
        gene=FLAGSHIP_GENE,
        genotype=FLAGSHIP_GENOTYPE,
        population=population,
        correlation_id="bias-test",
    )
    # Cover every facet.
    for facet in ALL_FACETS:
        base = base.with_facet(
            facet,
            state=FacetCoverageState.COVERED,
            evidence_refs=(f"src:{facet.value}",),
            reason="seeded",
        )
    # Optional override for POPULATION state.
    if pop_state is not FacetCoverageState.COVERED:
        base = base.with_facet(
            ClaimEvidenceFacet.POPULATION,
            state=pop_state,
            evidence_refs=(),
            reason="downgraded for test",
        )
    return base


@pytest.fixture
def detector() -> PopulationEvidenceBiasDetector:
    return PopulationEvidenceBiasDetector()


# ---------------------------------------------------------------------------
# Closed enum contract
# ---------------------------------------------------------------------------


class TestBiasKindEnum:
    def test_exactly_3_bias_kinds(self) -> None:
        assert len(list(BiasKind)) == 3

    def test_kind_values_are_stable(self) -> None:
        assert BiasKind.EUROCENTRIC_IMBALANCE.value == "eurocentric_imbalance"
        assert BiasKind.ANCESTRY_SCARCITY.value == "ancestry_scarcity"
        assert BiasKind.UNSUPPORTED_EXTRAPOLATION.value == "unsupported_extrapolation"


# ---------------------------------------------------------------------------
# Rule 1 — EUROCENTRIC_IMBALANCE
# ---------------------------------------------------------------------------


class TestEurocentricImbalance:
    def test_fires_when_non_eur_target_has_zero_evidence_and_eur_has_evidence(
        self, detector: PopulationEvidenceBiasDetector
    ) -> None:
        analysis = _analysis_for(SuperPopulation.SAS)
        indexer = make_pop_indexer(
            alleles={
                SuperPopulation.SAS: ["CYP2C19*2"],
                SuperPopulation.EUR: ["CYP2C19*2"],
            },
            evidence={
                SuperPopulation.SAS: [],  # zero
                SuperPopulation.EUR: ["PMID:eur1"],  # present
            },
        )
        findings = detector.detect(analysis, pop_indexer=indexer)
        kinds = {f.kind for f in findings}
        assert BiasKind.EUROCENTRIC_IMBALANCE in kinds

    def test_does_not_fire_when_target_is_eur(
        self, detector: PopulationEvidenceBiasDetector
    ) -> None:
        analysis = _analysis_for(SuperPopulation.EUR)
        indexer = make_pop_indexer(
            alleles={SuperPopulation.EUR: ["CYP2C19*2"]},
            evidence={SuperPopulation.EUR: []},
        )
        findings = detector.detect(analysis, pop_indexer=indexer)
        kinds = {f.kind for f in findings}
        assert BiasKind.EUROCENTRIC_IMBALANCE not in kinds

    def test_does_not_fire_when_target_has_evidence(
        self, detector: PopulationEvidenceBiasDetector
    ) -> None:
        analysis = _analysis_for(SuperPopulation.SAS)
        indexer = make_pop_indexer(
            alleles={SuperPopulation.SAS: ["CYP2C19*2"]},
            evidence={
                SuperPopulation.SAS: ["PMID:sas1"],
                SuperPopulation.EUR: ["PMID:eur1"],
            },
        )
        findings = detector.detect(analysis, pop_indexer=indexer)
        kinds = {f.kind for f in findings}
        assert BiasKind.EUROCENTRIC_IMBALANCE not in kinds

    def test_respects_min_target_evidence_threshold(self) -> None:
        detector = PopulationEvidenceBiasDetector(min_target_evidence=3)
        analysis = _analysis_for(SuperPopulation.SAS)
        # 2 target evidence < threshold 3, EUR has some.
        indexer = make_pop_indexer(
            alleles={
                SuperPopulation.SAS: ["a"],
                SuperPopulation.EUR: ["a"],
            },
            evidence={
                SuperPopulation.SAS: ["PMID:1", "PMID:2"],
                SuperPopulation.EUR: ["PMID:eur1"],
            },
        )
        findings = detector.detect(analysis, pop_indexer=indexer)
        kinds = {f.kind for f in findings}
        assert BiasKind.EUROCENTRIC_IMBALANCE in kinds


# ---------------------------------------------------------------------------
# Rule 2 — ANCESTRY_SCARCITY
# ---------------------------------------------------------------------------


class TestAncestryScarcity:
    def test_fires_when_target_count_below_scarcity_ratio(
        self, detector: PopulationEvidenceBiasDetector
    ) -> None:
        # Default scarcity_ratio = 0.5; target has 1/4 = 0.25 of max.
        analysis = _analysis_for(SuperPopulation.SAS)
        indexer = make_pop_indexer(
            alleles={
                SuperPopulation.SAS: ["a1"],  # 1
                SuperPopulation.EUR: ["a1", "a2", "a3", "a4"],  # 4 (max)
                SuperPopulation.AFR: ["a1", "a2"],  # 2
            },
            evidence={
                SuperPopulation.SAS: ["PMID:sas"],
                SuperPopulation.EUR: ["PMID:eur"],
            },
        )
        findings = detector.detect(analysis, pop_indexer=indexer)
        kinds = {f.kind for f in findings}
        assert BiasKind.ANCESTRY_SCARCITY in kinds

    def test_does_not_fire_when_target_count_at_or_above_ratio(
        self, detector: PopulationEvidenceBiasDetector
    ) -> None:
        analysis = _analysis_for(SuperPopulation.SAS)
        indexer = make_pop_indexer(
            alleles={
                SuperPopulation.SAS: ["a1", "a2", "a3"],  # 3
                SuperPopulation.EUR: ["a1", "a2", "a3", "a4"],  # 4
            },
            evidence={
                SuperPopulation.SAS: ["PMID:sas"],
                SuperPopulation.EUR: ["PMID:eur"],
            },
        )
        # ratio = 3/4 = 0.75 > 0.5 default -> no scarcity finding.
        findings = detector.detect(analysis, pop_indexer=indexer)
        kinds = {f.kind for f in findings}
        assert BiasKind.ANCESTRY_SCARCITY not in kinds

    def test_configurable_scarcity_ratio(self) -> None:
        # Even 3/4 = 0.75 fires scarcity at threshold 0.9.
        detector = PopulationEvidenceBiasDetector(scarcity_ratio=0.9)
        analysis = _analysis_for(SuperPopulation.SAS)
        indexer = make_pop_indexer(
            alleles={
                SuperPopulation.SAS: ["a1", "a2", "a3"],
                SuperPopulation.EUR: ["a1", "a2", "a3", "a4"],
            },
            evidence={
                SuperPopulation.SAS: ["PMID:sas"],
                SuperPopulation.EUR: ["PMID:eur"],
            },
        )
        findings = detector.detect(analysis, pop_indexer=indexer)
        kinds = {f.kind for f in findings}
        assert BiasKind.ANCESTRY_SCARCITY in kinds

    def test_no_findings_when_all_counts_zero(
        self, detector: PopulationEvidenceBiasDetector
    ) -> None:
        """Degenerate KG with no alleles at all — rule 2 cannot decide."""
        analysis = _analysis_for(SuperPopulation.SAS)
        indexer = make_pop_indexer(alleles={}, evidence={})
        findings = detector.detect(analysis, pop_indexer=indexer)
        # ANCESTRY_SCARCITY should not appear (max_count == 0 guard).
        kinds = {f.kind for f in findings}
        assert BiasKind.ANCESTRY_SCARCITY not in kinds


# ---------------------------------------------------------------------------
# Rule 3 — UNSUPPORTED_EXTRAPOLATION
# ---------------------------------------------------------------------------


class TestUnsupportedExtrapolation:
    def test_fires_when_population_uncertain_and_no_target_freq_data(
        self, detector: PopulationEvidenceBiasDetector
    ) -> None:
        analysis = _analysis_for(
            SuperPopulation.AFR,
            pop_state=FacetCoverageState.UNCERTAIN,
        )
        indexer = make_pop_indexer(
            alleles={
                SuperPopulation.EUR: ["a1", "a2"],
                # AFR explicitly absent / empty
            },
        )
        findings = detector.detect(analysis, pop_indexer=indexer)
        kinds = {f.kind for f in findings}
        assert BiasKind.UNSUPPORTED_EXTRAPOLATION in kinds

    def test_no_indexer_still_fires_when_population_uncertain(
        self, detector: PopulationEvidenceBiasDetector
    ) -> None:
        """Without an indexer, rule 3 still fires — the detector can't
        verify target coverage and must treat it as unsupported."""
        analysis = _analysis_for(
            SuperPopulation.AFR,
            pop_state=FacetCoverageState.UNCERTAIN,
        )
        findings = detector.detect(analysis, pop_indexer=None)
        kinds = {f.kind for f in findings}
        assert BiasKind.UNSUPPORTED_EXTRAPOLATION in kinds

    def test_does_not_fire_when_population_covered(
        self, detector: PopulationEvidenceBiasDetector
    ) -> None:
        analysis = _analysis_for(
            SuperPopulation.AFR,
            pop_state=FacetCoverageState.COVERED,
        )
        findings = detector.detect(analysis, pop_indexer=None)
        kinds = {f.kind for f in findings}
        assert BiasKind.UNSUPPORTED_EXTRAPOLATION not in kinds

    def test_does_not_fire_when_target_has_freq_data(
        self, detector: PopulationEvidenceBiasDetector
    ) -> None:
        analysis = _analysis_for(
            SuperPopulation.AFR,
            pop_state=FacetCoverageState.UNCERTAIN,
        )
        # Allele scoped to the analysis gene (CYP2C19, FLAGSHIP_GENE).
        # The bias detector now gene-scopes ``alleles_for`` lookups so
        # an allele under a different gene (e.g. CYP2D6*17) would no
        # longer count as freq data for an analysis on CYP2C19. Use a
        # gene-matching allele to test the rule's "has freq data"
        # branch.
        indexer = make_pop_indexer(
            alleles={SuperPopulation.AFR: ["CYP2C19*2"]},
        )
        findings = detector.detect(analysis, pop_indexer=indexer)
        kinds = {f.kind for f in findings}
        assert BiasKind.UNSUPPORTED_EXTRAPOLATION not in kinds


# ---------------------------------------------------------------------------
# Finding shape
# ---------------------------------------------------------------------------


class TestFindingShape:
    def test_finding_preserves_target_population(
        self, detector: PopulationEvidenceBiasDetector
    ) -> None:
        analysis = _analysis_for(SuperPopulation.SAS)
        indexer = make_pop_indexer(
            alleles={
                SuperPopulation.SAS: ["a1"],
                SuperPopulation.EUR: ["a1", "a2", "a3", "a4"],
            },
            evidence={
                SuperPopulation.SAS: [],
                SuperPopulation.EUR: ["PMID:eur"],
            },
        )
        findings = detector.detect(analysis, pop_indexer=indexer)
        assert all(f.target is SuperPopulation.SAS for f in findings)

    def test_finding_to_dict_is_jsonable(self, detector: PopulationEvidenceBiasDetector) -> None:
        import json

        analysis = _analysis_for(
            SuperPopulation.AFR,
            pop_state=FacetCoverageState.UNCERTAIN,
        )
        findings = detector.detect(analysis, pop_indexer=None)
        for f in findings:
            dumped = json.loads(json.dumps(f.to_dict()))
            assert dumped["kind"] in {
                "eurocentric_imbalance",
                "ancestry_scarcity",
                "unsupported_extrapolation",
            }
            assert dumped["target"] == "AFR"


# ---------------------------------------------------------------------------
# Determinism: same input -> same findings (sorted stably)
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_findings_are_stable_order(self, detector: PopulationEvidenceBiasDetector) -> None:
        analysis = _analysis_for(
            SuperPopulation.SAS,
            pop_state=FacetCoverageState.UNCERTAIN,
        )
        indexer = make_pop_indexer(
            alleles={
                SuperPopulation.SAS: ["a1"],
                SuperPopulation.EUR: ["a1", "a2", "a3", "a4"],
            },
            evidence={
                SuperPopulation.SAS: [],
                SuperPopulation.EUR: ["PMID:eur"],
            },
        )
        f1 = detector.detect(analysis, pop_indexer=indexer)
        f2 = detector.detect(analysis, pop_indexer=indexer)
        # Same kinds and reasons in the same order.
        assert [f.kind for f in f1] == [f.kind for f in f2]
        assert [f.reason for f in f1] == [f.reason for f in f2]

    def test_no_detection_with_no_inputs_returns_empty_tuple(
        self, detector: PopulationEvidenceBiasDetector
    ) -> None:
        analysis = _analysis_for(SuperPopulation.EUR)
        assert detector.detect(analysis) == ()
