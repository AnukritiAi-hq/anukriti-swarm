"""Closed-enum types and frozen records for cohort-scale simulation.

All types here follow the platform's closed-enum scope firewall
discipline. Adding a new value is a code change — which is exactly
what makes this a scope firewall.

See the package-level docstring in ``core/simulation/__init__.py``
for the full rationale and stage-1 data-access guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from core.models.population import SuperPopulation


# ---------------------------------------------------------------------------
# Scope — what kinds of cohort reasoning this package supports
# ---------------------------------------------------------------------------


class SimulationScope(str, Enum):
    """Closed enum of simulation scopes.

    The whole reason this enum exists is to prevent scope drift
    into "virtual clinical trials" or "PK/PD simulation" — both of
    which are either out of reach (data-access bound) or
    irresponsible (clinical-trial replacement is not something
    computational approaches achieve today).

    Three allowed values, ordered by ambition:

    ``COHORT_EVIDENCE_REASONING``
        Sample N synthetic genotypes from a real population-
        frequency distribution. Run each through the swarm's
        deterministic phenotype + sufficiency + verification
        pipeline. Aggregate the outcomes. **This is what we can
        ship today using public data.**

    ``CROSS_ANCESTRY_COMPARISON``
        Run the same drug query against multiple virtual
        populations, surface the differences in outcome
        distribution. Still Stage 1 (public data), but adds
        cross-population analysis.

    ``PRE_TRIAL_RISK_SURFACING``
        For a proposed trial enrollment plan (super-population
        proportions), surface the evidence-density risks before
        the trial starts. Natural extension. Still Stage 1.

    Deliberately NOT present:
    - ``PK_PD_SIMULATION`` — requires a pharmacokinetic modeling
      layer we do not have and would overclaim if we named.
    - ``VIRTUAL_CLINICAL_TRIAL`` — not a thing computational
      approaches achieve today. Regulators won't accept it.
      Naming it implies otherwise.
    """

    COHORT_EVIDENCE_REASONING = "cohort_evidence_reasoning"
    CROSS_ANCESTRY_COMPARISON = "cross_ancestry_comparison"
    PRE_TRIAL_RISK_SURFACING = "pre_trial_risk_surfacing"


# ---------------------------------------------------------------------------
# Sampling — how synthetic genotypes are drawn from the population
# ---------------------------------------------------------------------------


class CohortSamplingMethod(str, Enum):
    """Closed enum of sampling strategies for synthetic cohorts.

    ``HARDY_WEINBERG``
        Draw diplotypes assuming Hardy-Weinberg equilibrium given
        observed allele frequencies. Simple, defensible, matches
        how population-genetics textbooks compute expected
        phenotype proportions.

    ``FREQUENCY_WEIGHTED_PAIRING``
        Draw each allele independently from the population's
        allele-frequency distribution, pair to form a diplotype.
        Equivalent to Hardy-Weinberg for independent draws; named
        separately for cases where we want to make the
        independence assumption explicit.

    ``OBSERVED_DIPLOTYPE_FREQUENCIES``
        Draw from a diplotype-frequency distribution directly
        (rather than allele frequencies). Requires diplotype-
        level data which is rarer; supported as an extension
        point for when that data is available.
    """

    HARDY_WEINBERG = "hardy_weinberg"
    FREQUENCY_WEIGHTED_PAIRING = "frequency_weighted_pairing"
    OBSERVED_DIPLOTYPE_FREQUENCIES = "observed_diplotype_frequencies"


# ---------------------------------------------------------------------------
# Drug-safety outcome — aggregated across a cohort
# ---------------------------------------------------------------------------


class DrugSafetyOutcome(str, Enum):
    """Closed enum of drug-safety outcomes per synthetic patient.

    Intentionally narrow. These map directly to the CPIC
    recommendation categories we already support — no new outcome
    categories invented at the simulation layer.

    ``RECOMMENDED_AS_IS``
        Patient's phenotype + population + evidence support the
        standard CPIC recommendation with no modifications.

    ``RECOMMENDED_WITH_CAVEAT``
        Standard recommendation but with documented caveats
        (evidence sufficiency downgraded, or cross-ancestry hedge
        applied).

    ``CONTRAINDICATED``
        Drug should not be used for this patient; CPIC guideline
        says avoid.

    ``ALTERNATIVE_RECOMMENDED``
        Drug is contraindicated; a specific alternative is
        suggested per CPIC.

    ``REFUSED``
        Evidence insufficient to synthesize a recommendation (the
        system's honest-refusal outcome).

    The mapping from a swarm run's ``SufficiencyDecision`` +
    ``EvidenceVerdict`` to a ``DrugSafetyOutcome`` is deterministic
    and documented in ``cohort_demo.py``.
    """

    RECOMMENDED_AS_IS = "recommended_as_is"
    RECOMMENDED_WITH_CAVEAT = "recommended_with_caveat"
    CONTRAINDICATED = "contraindicated"
    ALTERNATIVE_RECOMMENDED = "alternative_recommended"
    REFUSED = "refused"


# ---------------------------------------------------------------------------
# Frozen records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SyntheticPatient:
    """A single synthetic patient in a cohort.

    Immutable once constructed. Built by sampling from a
    ``VirtualPopulation``'s allele-frequency distribution.

    Fields
    ------
    patient_id
        Stable identifier within a simulation run.
    super_population
        Which ``SuperPopulation`` the patient was sampled from.
    gene
        The pharmacogene the simulation is about (e.g. "CYP2C19").
    diplotype
        The sampled diplotype string (e.g. "*1/*2").
    sampling_method
        Which ``CohortSamplingMethod`` produced this patient.
    """

    patient_id: str
    super_population: SuperPopulation
    gene: str
    diplotype: str
    sampling_method: CohortSamplingMethod


@dataclass(frozen=True)
class VirtualPopulation:
    """A frequency-distribution backed synthetic cohort source.

    This is what we build cohort reasoning *over*. Stage-1
    constraint: the ``allele_frequencies`` must come from public
    or aggregate data (CPIC tables, 1000 Genomes, IndiGen public,
    GenomeAsia Pilot supplementary).

    Fields
    ------
    super_population
        Which ``SuperPopulation`` this represents (EUR / EAS / SAS
        / AFR / AMR).
    gene
        The pharmacogene the frequencies are about.
    allele_frequencies
        Mapping of allele name (e.g. "*1", "*2", "*17") to its
        observed frequency in this population. Frequencies should
        sum to ~1.0 within floating-point tolerance.
    source
        Provenance string (e.g. "CPIC:2022.1", "1000G:phase3",
        "IndiGen:2023"). Must be non-empty; simulations without
        data provenance are rejected at construction time.
    """

    super_population: SuperPopulation
    gene: str
    allele_frequencies: Mapping[str, float]
    source: str

    def __post_init__(self) -> None:
        """Validate construction-time invariants."""
        if not self.source:
            raise ValueError(
                "VirtualPopulation requires a non-empty source — "
                "simulations without data provenance are rejected"
            )
        if not self.allele_frequencies:
            raise ValueError(
                f"VirtualPopulation for {self.gene}+{self.super_population.value} "
                "has empty allele_frequencies"
            )
        # Allow small floating-point drift from 1.0 but flag gross errors
        total = sum(self.allele_frequencies.values())
        if not 0.95 <= total <= 1.05:
            raise ValueError(
                f"VirtualPopulation allele frequencies sum to {total:.4f}, "
                f"expected ~1.0 — check source data for {self.gene}+"
                f"{self.super_population.value}"
            )


@dataclass(frozen=True)
class SimulationRun:
    """Frozen record of a completed cohort simulation.

    Produced by the cohort demo (and eventually a programmatic
    cohort runner). Captures the full inputs and outputs so the
    run is replayable and auditable.

    Fields
    ------
    run_id
        Unique identifier (typically derived from correlation_id
        + timestamp).
    scope
        Which ``SimulationScope`` this run was.
    super_population
        The primary population for the run.
    gene
        The pharmacogene simulated over.
    drug
        The drug the safety question is about.
    cohort_size
        Number of ``SyntheticPatient`` records in the cohort.
    sampling_method
        Which ``CohortSamplingMethod`` produced the cohort.
    outcome_distribution
        Mapping of ``DrugSafetyOutcome.value`` -> count across the
        cohort. Keys sum to ``cohort_size``.
    source_populations
        Tuple of the ``VirtualPopulation`` sources the run drew
        from (cross-ancestry runs will have multiple).
    created_at
        UTC timestamp of run completion.
    """

    run_id: str
    scope: SimulationScope
    super_population: SuperPopulation
    gene: str
    drug: str
    cohort_size: int
    sampling_method: CohortSamplingMethod
    outcome_distribution: Mapping[str, int]
    source_populations: tuple[VirtualPopulation, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Validate that outcome counts sum to cohort_size."""
        total = sum(self.outcome_distribution.values())
        if total != self.cohort_size:
            raise ValueError(
                f"SimulationRun outcome_distribution sums to {total}, "
                f"expected cohort_size={self.cohort_size}"
            )

    def outcome_fraction(self, outcome: DrugSafetyOutcome) -> float:
        """Fraction of cohort receiving this outcome."""
        if self.cohort_size == 0:
            return 0.0
        return self.outcome_distribution.get(outcome.value, 0) / self.cohort_size


__all__ = [
    "CohortSamplingMethod",
    "DrugSafetyOutcome",
    "SimulationRun",
    "SimulationScope",
    "SyntheticPatient",
    "VirtualPopulation",
]
