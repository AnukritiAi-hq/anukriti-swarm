"""Per-workflow allele-frequency tables and outcome mappers.

This module extends ``demos/cohort_demo`` to support the three
frontend workflows (clopidogrel, warfarin, simvastatin) without
modifying ``cohort_demo`` itself. The original module remains
byte-identical for the regression contract; this one is the single
source of truth for cohort-scale generation across the workflow
catalog.

Stage-1 data only. Sources for every population are public/aggregate:

  * **CYP2C19** — CPIC 2022.1 + PharmGKB PA166169660 + 1000G phase3
  * **CYP2C9**  — CPIC 2017 (warfarin) + PharmGKB PA126 + 1000G phase3
  * **VKORC1**  — CPIC 2017 + PharmGKB PA133787052 + 1000G phase3
  * **SLCO1B1** — CPIC 2022 (simvastatin) + PharmGKB PA134865839 + 1000G phase3

The tables here collapse the full allele catalog into the small subset
that drives the clinically-relevant phenotype split for each workflow.
This is the same simplification ``cohort_demo`` already uses for
CYP2C19 and is honest about: a finer-grained sub-population layer
(IndianRegion, CommunityLevel) is on the roadmap and would refine
these numbers.
"""
from __future__ import annotations

from core.models.population import SuperPopulation
from core.simulation import DrugSafetyOutcome


# ---------------------------------------------------------------------------
# CYP2C19 + clopidogrel — same numbers as cohort_demo (preserved)
# ---------------------------------------------------------------------------

CYP2C19_FREQS: dict[SuperPopulation, dict[str, float]] = {
    SuperPopulation.EUR: {"*1": 0.68, "*2": 0.15, "*17": 0.17},
    SuperPopulation.EAS: {"*1": 0.68, "*2": 0.30, "*17": 0.02},
    SuperPopulation.SAS: {"*1": 0.54, "*2": 0.36, "*17": 0.10},
    SuperPopulation.AFR: {"*1": 0.65, "*2": 0.18, "*17": 0.17},
    SuperPopulation.AMR: {"*1": 0.69, "*2": 0.18, "*17": 0.13},
}

CYP2C19_DIPLOTYPE_TO_PHENOTYPE: dict[str, str] = {
    "*1/*1": "Normal Metabolizer",
    "*1/*2": "Intermediate Metabolizer",
    "*2/*2": "Poor Metabolizer",
    "*1/*17": "Rapid Metabolizer",
    "*2/*17": "Intermediate Metabolizer",
    "*17/*17": "Ultrarapid Metabolizer",
}

CYP2C19_PHENOTYPE_TO_OUTCOME: dict[str, DrugSafetyOutcome] = {
    "Normal Metabolizer": DrugSafetyOutcome.RECOMMENDED_AS_IS,
    "Rapid Metabolizer": DrugSafetyOutcome.RECOMMENDED_AS_IS,
    "Ultrarapid Metabolizer": DrugSafetyOutcome.RECOMMENDED_AS_IS,
    "Intermediate Metabolizer": DrugSafetyOutcome.RECOMMENDED_WITH_CAVEAT,
    "Poor Metabolizer": DrugSafetyOutcome.ALTERNATIVE_RECOMMENDED,
}


# ---------------------------------------------------------------------------
# CYP2C9 + warfarin — Stage-1 simplified to *1 / *2 / *3
# ---------------------------------------------------------------------------
#
# Source: CPIC 2017 warfarin guideline (Johnson et al., PMID:28198005).
# 1000 Genomes phase3 super-population frequencies for rs1799853 (*2)
# and rs1057910 (*3). *1 = wildtype, captures the residual (other
# rare alleles like *5/*6/*8/*11 are <2% in every super-population
# and folded here into the *1 bucket for the Stage-1 demo).
#
# Numbers cross-checked against PharmGKB + 1000G; rounded to 2 sig figs.

CYP2C9_FREQS: dict[SuperPopulation, dict[str, float]] = {
    SuperPopulation.EUR: {"*1": 0.79, "*2": 0.13, "*3": 0.08},
    SuperPopulation.EAS: {"*1": 0.95, "*2": 0.01, "*3": 0.04},
    SuperPopulation.SAS: {"*1": 0.86, "*2": 0.05, "*3": 0.09},
    SuperPopulation.AFR: {"*1": 0.94, "*2": 0.02, "*3": 0.04},
    SuperPopulation.AMR: {"*1": 0.83, "*2": 0.10, "*3": 0.07},
}

# Per CPIC 2017 Table 2 — warfarin sensitivity by CYP2C9 diplotype.
CYP2C9_DIPLOTYPE_TO_PHENOTYPE: dict[str, str] = {
    "*1/*1": "Normal Metabolizer",
    "*1/*2": "Intermediate Metabolizer",
    "*1/*3": "Intermediate Metabolizer",
    "*2/*2": "Intermediate Metabolizer",
    "*2/*3": "Poor Metabolizer",
    "*3/*3": "Poor Metabolizer",
}

CYP2C9_PHENOTYPE_TO_OUTCOME: dict[str, DrugSafetyOutcome] = {
    "Normal Metabolizer": DrugSafetyOutcome.RECOMMENDED_AS_IS,
    "Intermediate Metabolizer": DrugSafetyOutcome.RECOMMENDED_WITH_CAVEAT,
    "Poor Metabolizer": DrugSafetyOutcome.ALTERNATIVE_RECOMMENDED,
}


# ---------------------------------------------------------------------------
# SLCO1B1 + simvastatin — Stage-1 simplified to *1 / *5
# ---------------------------------------------------------------------------
#
# Source: CPIC 2022 simvastatin guideline (Cooper-DeHoff et al.,
# PMID:35152405). rs4149056 is the c.521T>C variant defining *5;
# *1 captures the residual.
#
# Frequencies for rs4149056 across super-populations (1000G phase3,
# verified against gnomAD v4.0):

SLCO1B1_FREQS: dict[SuperPopulation, dict[str, float]] = {
    SuperPopulation.EUR: {"*1": 0.84, "*5": 0.16},
    SuperPopulation.EAS: {"*1": 0.86, "*5": 0.14},
    SuperPopulation.SAS: {"*1": 0.82, "*5": 0.18},
    SuperPopulation.AFR: {"*1": 0.99, "*5": 0.01},
    SuperPopulation.AMR: {"*1": 0.84, "*5": 0.16},
}

SLCO1B1_DIPLOTYPE_TO_PHENOTYPE: dict[str, str] = {
    "*1/*1": "Normal Function",
    "*1/*5": "Decreased Function",
    "*5/*5": "Poor Function",
}

# Per CPIC 2022: Decreased Function -> recommend max 20mg/day or
# alternative; Poor Function -> alternative recommended.
SLCO1B1_PHENOTYPE_TO_OUTCOME: dict[str, DrugSafetyOutcome] = {
    "Normal Function": DrugSafetyOutcome.RECOMMENDED_AS_IS,
    "Decreased Function": DrugSafetyOutcome.RECOMMENDED_WITH_CAVEAT,
    "Poor Function": DrugSafetyOutcome.ALTERNATIVE_RECOMMENDED,
}


# ---------------------------------------------------------------------------
# Sources (provenance strings for the VirtualPopulation record)
# ---------------------------------------------------------------------------

WORKFLOW_SOURCES: dict[str, str] = {
    "clopidogrel": "CPIC:CYP2C19:clopidogrel:2022.1+PharmGKB:PA166169660+1000G:phase3",
    "warfarin":    "CPIC:CYP2C9:warfarin:2017+PharmGKB:PA126+1000G:phase3",
    "simvastatin": "CPIC:SLCO1B1:simvastatin:2022+PharmGKB:PA134865839+1000G:phase3",
}


# ---------------------------------------------------------------------------
# Public registry — keyed by workflow id used by the API
# ---------------------------------------------------------------------------


WORKFLOW_TABLES: dict[str, dict[str, object]] = {
    "clopidogrel": {
        "gene": "CYP2C19",
        "drug": "clopidogrel",
        "freqs": CYP2C19_FREQS,
        "diplotype_to_phenotype": CYP2C19_DIPLOTYPE_TO_PHENOTYPE,
        "phenotype_to_outcome": CYP2C19_PHENOTYPE_TO_OUTCOME,
        "source": WORKFLOW_SOURCES["clopidogrel"],
    },
    "warfarin": {
        "gene": "CYP2C9",
        "drug": "warfarin",
        "freqs": CYP2C9_FREQS,
        "diplotype_to_phenotype": CYP2C9_DIPLOTYPE_TO_PHENOTYPE,
        "phenotype_to_outcome": CYP2C9_PHENOTYPE_TO_OUTCOME,
        "source": WORKFLOW_SOURCES["warfarin"],
    },
    "simvastatin": {
        "gene": "SLCO1B1",
        "drug": "simvastatin",
        "freqs": SLCO1B1_FREQS,
        "diplotype_to_phenotype": SLCO1B1_DIPLOTYPE_TO_PHENOTYPE,
        "phenotype_to_outcome": SLCO1B1_PHENOTYPE_TO_OUTCOME,
        "source": WORKFLOW_SOURCES["simvastatin"],
    },
}


def get_workflow(workflow_id: str) -> dict[str, object]:
    if workflow_id not in WORKFLOW_TABLES:
        raise KeyError(f"unknown workflow {workflow_id!r}; expected one of {sorted(WORKFLOW_TABLES)}")
    return WORKFLOW_TABLES[workflow_id]


__all__ = [
    "WORKFLOW_TABLES",
    "WORKFLOW_SOURCES",
    "get_workflow",
    # CYP2C19
    "CYP2C19_FREQS",
    "CYP2C19_DIPLOTYPE_TO_PHENOTYPE",
    "CYP2C19_PHENOTYPE_TO_OUTCOME",
    # CYP2C9
    "CYP2C9_FREQS",
    "CYP2C9_DIPLOTYPE_TO_PHENOTYPE",
    "CYP2C9_PHENOTYPE_TO_OUTCOME",
    # SLCO1B1
    "SLCO1B1_FREQS",
    "SLCO1B1_DIPLOTYPE_TO_PHENOTYPE",
    "SLCO1B1_PHENOTYPE_TO_OUTCOME",
]
