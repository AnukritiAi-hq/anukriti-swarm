"""Cohort-scale PGx reasoning demo — Stage 1 public-data simulation.

Runs a 100-patient Monte Carlo across five super-populations,
using real CPIC-derived allele frequencies from the knowledge-
graph seed, and surfaces the drug-safety outcome distribution
per population.

Canonical scenario
------------------
**Clopidogrel + CYP2C19.** The most well-studied PGx scenario in
our platform, with real frequency data across EUR, EAS, SAS, AFR
(our seed includes all four; AMR is extrapolated at ~0.18 from
public references for demonstration).

What the demo shows
-------------------
Running the same gene + drug question over a 100-patient synthetic
cohort sampled from each super-population's real allele-frequency
distribution makes the population-dependent safety delta concrete:

- SAS (CYP2C19*2 frequency 0.36) produces ~13% Poor Metabolizers
  who need clopidogrel alternatives
- EAS (0.30) produces ~9%
- AFR (0.18) produces ~3%
- EUR (0.15) produces ~2%
- AMR (~0.18) produces ~3%

These are the **expected Hardy-Weinberg predictions** from
published allele frequencies. No clinical-trial replacement is
claimed — this is cohort-scale *evidence reasoning*, not
simulation of pharmacokinetics.

Stage 1 guarantee
-----------------
Every input is public or aggregate data:

- CPIC 2022.1 recommendation for clopidogrel + CYP2C19
- 1000 Genomes-derived super-population allele frequencies
  (ingested into our KG seed with PharmGKB/PubMed provenance)
- Hardy-Weinberg assumption (standard population-genetics baseline)

No controlled-access data is used. This demo runs from a clean
checkout with no external credentials.

See anukriti-pgx-core/docs/strategy.md for the tier framework and
anukriti-pgx-core/docs/adr/0002-positioning-as-infrastructure.md
for the positioning this demo operationalizes.

Run
---
    python -m demos.cohort_demo

Output: a per-population outcome distribution table + an
aggregated `SimulationRun` summary per population. Deterministic
given the fixed RNG seed.
"""

from __future__ import annotations

import random
from uuid import uuid4

from core.models.population import SuperPopulation
from core.simulation import (
    CohortSamplingMethod,
    DrugSafetyOutcome,
    SimulationRun,
    SimulationScope,
    SyntheticPatient,
    VirtualPopulation,
)

# ---------------------------------------------------------------------------
# Canonical scenario — CYP2C19 + clopidogrel
# ---------------------------------------------------------------------------

GENE = "CYP2C19"
DRUG = "clopidogrel"
COHORT_SIZE = 100
RNG_SEED = 42  # Deterministic across runs — every demo run gives same output.


# Per-population CYP2C19 allele frequencies from the KG seed
# (knowledge_graph/seed.py). *2 is the main loss-of-function
# variant. For Stage 1 we collapse to a 3-allele model:
#   *1  — wildtype / functional
#   *2  — loss-of-function (the major clopidogrel-relevant allele)
#   *17 — gain-of-function (RM/UM contributor)
#
# Frequencies are super-population averages; sub-populations
# (SAS:GIH, SAS:BEB, etc.) would produce finer-grained numbers
# but require the sub-population ANCESTRY node kind which is
# currently a populated extension point (not seeded).

POPULATION_FREQUENCIES: dict[SuperPopulation, dict[str, float]] = {
    SuperPopulation.EUR: {"*1": 0.68, "*2": 0.15, "*17": 0.17},
    SuperPopulation.EAS: {"*1": 0.68, "*2": 0.30, "*17": 0.02},
    SuperPopulation.SAS: {"*1": 0.54, "*2": 0.36, "*17": 0.10},
    SuperPopulation.AFR: {"*1": 0.65, "*2": 0.18, "*17": 0.17},
    SuperPopulation.AMR: {"*1": 0.69, "*2": 0.18, "*17": 0.13},
}

# Sources per population (provenance — each edge in a real run
# would carry one of these).
POPULATION_SOURCES: dict[SuperPopulation, str] = {
    SuperPopulation.EUR: "PharmGKB:PA166169660+1000G:phase3",
    SuperPopulation.EAS: "PharmGKB:PA166169660+1000G:phase3",
    SuperPopulation.SAS: "PharmGKB:PA166169660+1000G:phase3",
    SuperPopulation.AFR: "PharmGKB:PA166169660+1000G:phase3",
    SuperPopulation.AMR: "PharmGKB:PA166169660+1000G:phase3",
}


# ---------------------------------------------------------------------------
# Diplotype → phenotype → outcome mapping (CPIC 2022.1)
# ---------------------------------------------------------------------------
#
# This is the deterministic CPIC table applied per-patient. Real
# pgx-core handles the full phenotype engine; this demo uses a
# simplified subset for CYP2C19 + clopidogrel.

DIPLOTYPE_TO_PHENOTYPE: dict[str, str] = {
    "*1/*1": "Normal Metabolizer",
    "*1/*2": "Intermediate Metabolizer",
    "*2/*2": "Poor Metabolizer",
    "*1/*17": "Rapid Metabolizer",
    "*2/*17": "Intermediate Metabolizer",  # CPIC 2022 named-diplotype lookup
    "*17/*17": "Ultrarapid Metabolizer",
}

# CYP2C19 phenotype → clopidogrel outcome (per CPIC 2022.1
# guideline). PMs and IMs get alternative antiplatelet
# recommendations; NMs, RMs, UMs use clopidogrel as-is.
PHENOTYPE_TO_OUTCOME: dict[str, DrugSafetyOutcome] = {
    "Normal Metabolizer": DrugSafetyOutcome.RECOMMENDED_AS_IS,
    "Rapid Metabolizer": DrugSafetyOutcome.RECOMMENDED_AS_IS,
    "Ultrarapid Metabolizer": DrugSafetyOutcome.RECOMMENDED_AS_IS,
    "Intermediate Metabolizer": DrugSafetyOutcome.RECOMMENDED_WITH_CAVEAT,
    "Poor Metabolizer": DrugSafetyOutcome.ALTERNATIVE_RECOMMENDED,
}


# ---------------------------------------------------------------------------
# Cohort sampling — Hardy-Weinberg from real allele frequencies
# ---------------------------------------------------------------------------


def _canonical_diplotype(a1: str, a2: str) -> str:
    """Order a diplotype by CPIC numeric-suffix convention.

    \\*2/\\*17 is canonical, not \\*17/\\*2. Matches the
    diplotype-table keys used above.
    """
    # Strip leading * for numeric comparison
    n1 = int(a1.lstrip("*")) if a1.lstrip("*").isdigit() else 0
    n2 = int(a2.lstrip("*")) if a2.lstrip("*").isdigit() else 0
    if n1 <= n2:
        return f"{a1}/{a2}"
    return f"{a2}/{a1}"


def _sample_diplotype(
    rng: random.Random,
    allele_frequencies: dict[str, float],
) -> str:
    """Draw a single diplotype assuming Hardy-Weinberg equilibrium.

    Each of the two alleles is drawn independently from the same
    frequency distribution. This matches the
    ``FREQUENCY_WEIGHTED_PAIRING`` semantics of the
    ``CohortSamplingMethod`` enum (equivalent to Hardy-Weinberg
    for independent draws; we use the HARDY_WEINBERG label here
    to make the population-genetics provenance explicit).
    """
    alleles = list(allele_frequencies.keys())
    weights = list(allele_frequencies.values())
    a1 = rng.choices(alleles, weights=weights, k=1)[0]
    a2 = rng.choices(alleles, weights=weights, k=1)[0]
    return _canonical_diplotype(a1, a2)


def _sample_cohort(
    population: SuperPopulation,
    size: int,
    rng: random.Random,
) -> tuple[list[SyntheticPatient], VirtualPopulation]:
    """Sample ``size`` synthetic patients from ``population``.

    Returns the patient list and the ``VirtualPopulation`` record
    that was used as the sampling source.
    """
    freqs = POPULATION_FREQUENCIES[population]
    source = POPULATION_SOURCES[population]

    virtual_pop = VirtualPopulation(
        super_population=population,
        gene=GENE,
        allele_frequencies=freqs,
        source=source,
    )

    patients: list[SyntheticPatient] = []
    for i in range(size):
        diplotype = _sample_diplotype(rng, freqs)
        patients.append(
            SyntheticPatient(
                patient_id=f"{population.value}-{i:03d}",
                super_population=population,
                gene=GENE,
                diplotype=diplotype,
                sampling_method=CohortSamplingMethod.HARDY_WEINBERG,
            )
        )
    return patients, virtual_pop


# ---------------------------------------------------------------------------
# Per-patient outcome
# ---------------------------------------------------------------------------


def _outcome_for_patient(patient: SyntheticPatient) -> DrugSafetyOutcome:
    """Map one patient's diplotype to a clopidogrel outcome.

    Deterministic lookup: diplotype → phenotype → outcome. Any
    diplotype not in our simplified table falls back to REFUSED
    (the honest-refusal outcome; maps to what the real sufficiency
    engine would produce for an unknown diplotype).
    """
    phenotype = DIPLOTYPE_TO_PHENOTYPE.get(patient.diplotype)
    if phenotype is None:
        return DrugSafetyOutcome.REFUSED
    return PHENOTYPE_TO_OUTCOME[phenotype]


# ---------------------------------------------------------------------------
# Cohort aggregation
# ---------------------------------------------------------------------------


def _run_cohort_for_population(
    population: SuperPopulation,
    size: int,
    rng: random.Random,
) -> SimulationRun:
    """Run the cohort for one population; return a SimulationRun."""
    patients, virtual_pop = _sample_cohort(population, size, rng)

    counts: dict[str, int] = {o.value: 0 for o in DrugSafetyOutcome}
    for p in patients:
        outcome = _outcome_for_patient(p)
        counts[outcome.value] += 1

    return SimulationRun(
        run_id=f"cohort-{population.value}-{uuid4().hex[:8]}",
        scope=SimulationScope.CROSS_ANCESTRY_COMPARISON,
        super_population=population,
        gene=GENE,
        drug=DRUG,
        cohort_size=size,
        sampling_method=CohortSamplingMethod.HARDY_WEINBERG,
        outcome_distribution=counts,
        source_populations=(virtual_pop,),
    )


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------

_HEADER = "\033[1m"
_DIM = "\033[2m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_RESET = "\033[0m"


def _render_banner() -> None:
    print()
    print(f"  {_HEADER}{'═' * 68}{_RESET}")
    print(f"  {_HEADER}{_CYAN}  🧬 COHORT-SCALE PGx SIMULATION — STAGE 1 (PUBLIC DATA){_RESET}")
    print(f"  {_HEADER}{'═' * 68}{_RESET}")
    print(f"  {_DIM}  gene={GENE}  drug={DRUG}  cohort_size={COHORT_SIZE}{_RESET}")
    print(
        f"  {_DIM}  sampling={CohortSamplingMethod.HARDY_WEINBERG.value}  rng_seed={RNG_SEED}{_RESET}"
    )
    print(f"  {_DIM}  source=CPIC 2022.1 + PharmGKB PA166169660 + 1000G phase3{_RESET}")
    print()


def _render_scorecard(runs: list[SimulationRun]) -> None:
    print(f"  {_HEADER}{'─' * 92}{_RESET}")
    print(
        f"  {_HEADER}"
        f"{'Population':<12}"
        f"{'Rec as-is':>12}"
        f"{'With caveat':>14}"
        f"{'Alternative':>14}"
        f"{'Contra':>10}"
        f"{'Refused':>10}"
        f"{'PM %':>8}"
        f"{_RESET}"
    )
    print(f"  {_HEADER}{'─' * 92}{_RESET}")

    for run in runs:
        d = run.outcome_distribution
        pm_pct = run.outcome_fraction(DrugSafetyOutcome.ALTERNATIVE_RECOMMENDED) * 100
        # Color high PM% to make the population delta visually obvious.
        if pm_pct >= 10:
            pm_color = _RED
        elif pm_pct >= 5:
            pm_color = _YELLOW
        else:
            pm_color = _GREEN
        print(
            f"  {run.super_population.value:<12}"
            f"{d.get('recommended_as_is', 0):>12}"
            f"{d.get('recommended_with_caveat', 0):>14}"
            f"{d.get('alternative_recommended', 0):>14}"
            f"{d.get('contraindicated', 0):>10}"
            f"{d.get('refused', 0):>10}"
            f"{pm_color}{pm_pct:>7.1f}%{_RESET}"
        )
    print(f"  {_HEADER}{'─' * 92}{_RESET}")
    print()


def _render_interpretation(runs: list[SimulationRun]) -> None:
    print(f"  {_HEADER}  Interpretation{_RESET}")
    print()
    # Sort by PM fraction descending — surfaces the highest-risk
    # populations first, which is the point.
    sorted_runs = sorted(
        runs,
        key=lambda r: r.outcome_fraction(DrugSafetyOutcome.ALTERNATIVE_RECOMMENDED),
        reverse=True,
    )
    highest = sorted_runs[0]
    lowest = sorted_runs[-1]
    highest_pm = highest.outcome_fraction(DrugSafetyOutcome.ALTERNATIVE_RECOMMENDED) * 100
    lowest_pm = lowest.outcome_fraction(DrugSafetyOutcome.ALTERNATIVE_RECOMMENDED) * 100
    ratio = highest_pm / max(lowest_pm, 0.1)

    print(
        f"  {_DIM}  • {highest.super_population.value} shows the highest "
        f"alternative-recommended rate ({highest_pm:.1f}%).{_RESET}"
    )
    print(
        f"  {_DIM}  • {lowest.super_population.value} shows the lowest "
        f"({lowest_pm:.1f}%).{_RESET}"
    )
    print(f"  {_DIM}  • That's a {ratio:.1f}x delta — the clinical signal is real.{_RESET}")
    print()
    print(
        f"  {_DIM}  A population-blind prescribing protocol would under-serve "
        f"{highest.super_population.value} patients{_RESET}"
    )
    print(
        f"  {_DIM}  and over-warn {lowest.super_population.value} patients "
        f"— identically wrong, opposite direction.{_RESET}"
    )
    print()


def _render_footer() -> None:
    print(f"  {_HEADER}{'═' * 68}{_RESET}")
    print(f"  {_HEADER}{_CYAN}  Evidence-governed drug safety infrastructure —{_RESET}")
    print(f"  {_HEADER}{_CYAN}  population-aware by design.{_RESET}")
    print(f"  {_HEADER}{'═' * 68}{_RESET}")
    print()
    print(
        f"  {_DIM}  Stage 1 constraint: all data public or aggregate "
        f"(CPIC, 1000G, PharmGKB).{_RESET}"
    )
    print(
        f"  {_DIM}  Stage 2/3 datasets (All of Us, H3Africa, GenomeIndia) "
        f"are on the roadmap —{_RESET}"
    )
    print(f"  {_DIM}  see anukriti-pgx-core/docs/research-partnerships.md.{_RESET}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    rng = random.Random(RNG_SEED)

    _render_banner()

    runs: list[SimulationRun] = []
    for population in [
        SuperPopulation.EUR,
        SuperPopulation.EAS,
        SuperPopulation.SAS,
        SuperPopulation.AFR,
        SuperPopulation.AMR,
    ]:
        run = _run_cohort_for_population(population, COHORT_SIZE, rng)
        runs.append(run)

    _render_scorecard(runs)
    _render_interpretation(runs)
    _render_footer()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
