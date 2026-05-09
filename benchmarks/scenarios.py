"""Benchmark scenario definitions.

Reproducible test scenarios across genes and populations demonstrating:
"The same drug produces different genomic risk interpretations across populations."
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BenchmarkScenario:
    """A single benchmark scenario with expected outputs."""

    scenario_id: str
    gene: str
    drug: str
    population: str
    allele1: str
    allele2: str
    # Expected deterministic outputs
    expected_phenotype: str
    expected_risk: str
    expected_verdict: str
    # Population context
    expected_frequency: float | None = None
    expected_rarity: str = ""
    description: str = ""


# --- CYP2C19 / Clopidogrel across populations ---

CYP2C19_SCENARIOS: list[BenchmarkScenario] = [
    BenchmarkScenario(
        "cyp2c19_clop_sas_pm", "CYP2C19", "clopidogrel", "SAS", "*2", "*2",
        "Poor Metabolizer", "high_risk", "pass",
        0.36, "common",
        "South Asian PM — 14% prevalence, clopidogrel resistance crisis",
    ),
    BenchmarkScenario(
        "cyp2c19_clop_eur_pm", "CYP2C19", "clopidogrel", "EUR", "*2", "*2",
        "Poor Metabolizer", "high_risk", "pass",
        0.15, "common",
        "European PM — 2% prevalence, well-studied in guidelines",
    ),
    BenchmarkScenario(
        "cyp2c19_clop_afr_im", "CYP2C19", "clopidogrel", "AFR", "*1", "*2",
        "Intermediate Metabolizer", "high_risk", "pass",
        0.18, "common",
        "African IM — moderate frequency, standard guidelines apply",
    ),
    BenchmarkScenario(
        "cyp2c19_clop_sas_nm", "CYP2C19", "clopidogrel", "SAS", "*1", "*1",
        "Normal Metabolizer", "standard", "pass",
        None, "",
        "South Asian NM — clopidogrel effective",
    ),
    BenchmarkScenario(
        "cyp2c19_clop_eur_rm", "CYP2C19", "clopidogrel", "EUR", "*1", "*17",
        "Rapid Metabolizer", "standard", "pass",
        0.22, "common",
        # CPIC 2022 clopidogrel guideline (Table 2, NBK84114):
        # *1/*17 -> Rapid Metabolizer. Standard 75 mg/day dose is still
        # recommended for RM and UM; no increased bleeding risk observed.
        # See rules.phenotype_rules for the activity-score derivation
        # (*1=1.0 + *17=1.5 = 2.5 = RM).
        "European *1/*17 Rapid Metabolizer (CPIC 2022) — clopidogrel at standard dose",
    ),
]

# --- CYP2D6 / Codeine across populations ---

CYP2D6_SCENARIOS: list[BenchmarkScenario] = [
    BenchmarkScenario(
        "cyp2d6_codeine_eur_pm", "CYP2D6", "codeine", "EUR", "*4", "*4",
        "Poor Metabolizer", "high_risk", "pass",
        0.22, "common",
        "European PM — *4 is most common null allele here",
    ),
    BenchmarkScenario(
        # Scenario id kept as ..._afr_nm (was ..._afr_im) to reflect the
        # corrected CPIC-compliant phenotype assignment. The AFR population
        # context is preserved because *17 is still AFR-specific (~20%) —
        # the population-awareness claim stands; only the phenotype label
        # was wrong.
        "cyp2d6_codeine_afr_nm", "CYP2D6", "codeine", "AFR", "*1", "*17",
        "Normal Metabolizer", "standard", "pass",
        0.20, "common",
        # CPIC 2019 CYP2D6 genotype-to-phenotype standardization
        # (Caudle et al. 2020, PMID:31647186) + CYP2D6 allele
        # functionality table: *17 activity score = 0.5. Diplotype
        # score *1/*17 = 1.5 falls in NM band (>1.25 and <=2.25).
        # Pre-2019 conventions placed 1.5 in IM; superseded.
        # See rules.phenotype_rules PHENOTYPE_RANGES for the cutoffs.
        "African *1/*17 Normal Metabolizer (CPIC 2019 standardization) — "
        "*17 is AFR-specific (~20%); score 1.5 maps to NM, not IM as in "
        "pre-2019 conventions",
    ),
    BenchmarkScenario(
        "cyp2d6_codeine_sas_im", "CYP2D6", "codeine", "SAS", "*1", "*4",
        "Intermediate Metabolizer", "moderate_risk", "pass",
        0.09, "common",
        "South Asian IM — *4 at moderate frequency",
    ),
    BenchmarkScenario(
        "cyp2d6_codeine_eur_nm", "CYP2D6", "codeine", "EUR", "*1", "*2",
        "Normal Metabolizer", "standard", "pass",
        0.25, "common",
        "European NM — codeine effective at standard dose",
    ),
]

# --- HLA-B / Carbamazepine across populations ---

HLA_B_SCENARIOS: list[BenchmarkScenario] = [
    BenchmarkScenario(
        "hlab_cbz_eas_pos", "HLA-B", "carbamazepine", "EAS", "*15:02", "positive",
        "HLA-B*15:02 positive", "contraindicated", "pass",
        None, "",
        "East Asian *15:02 carrier (8%) — carbamazepine CONTRAINDICATED",
    ),
    BenchmarkScenario(
        "hlab_cbz_sas_pos", "HLA-B", "carbamazepine", "SAS", "*15:02", "positive",
        "HLA-B*15:02 positive", "contraindicated", "pass",
        None, "",
        "South Asian *15:02 carrier (4%) — carbamazepine CONTRAINDICATED",
    ),
    BenchmarkScenario(
        "hlab_cbz_eur_neg", "HLA-B", "carbamazepine", "EUR", "*15:02", "negative",
        "HLA-B*15:02 negative", "standard", "pass",
        None, "",
        "European non-carrier (<0.1%) — carbamazepine safe from HLA perspective",
    ),
]

ALL_SCENARIOS = CYP2C19_SCENARIOS + CYP2D6_SCENARIOS + HLA_B_SCENARIOS
