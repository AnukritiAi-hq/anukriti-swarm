"""CPIC guideline data for pharmacogenomic recommendations.

Contains versioned guideline recommendations for CYP2D6, CYP2C19, and HLA-B.
Data is structured for deterministic lookup by gene/phenotype/drug.

Sources:
- CPIC® Guidelines (https://cpicpgx.org/guidelines/)
- PharmGKB Clinical Annotations

Future: Will support DPWG, RNPGx, and automatic guideline update detection.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CPICRecommendation:
    """A single CPIC guideline recommendation."""

    gene: str
    phenotype: str
    drug: str
    recommendation: str
    strength: str           # "strong", "moderate", "optional"
    guideline_id: str       # e.g., "CPIC:CYP2D6:codeine:2023"
    guideline_version: str
    pmid: str
    classification: str     # "actionable", "informative"


# --- CYP2D6 Guidelines (CPIC 2023) ---

CYP2D6_GUIDELINES: list[CPICRecommendation] = [
    CPICRecommendation(
        "CYP2D6", "Poor Metabolizer", "codeine",
        "Avoid codeine. Use alternative analgesic (non-tramadol opioid or non-opioid).",
        "strong", "CPIC:CYP2D6:codeine:2023", "2023.1", "PMID:32722396", "actionable",
    ),
    CPICRecommendation(
        "CYP2D6", "Intermediate Metabolizer", "codeine",
        "Use codeine with caution at lowest effective dose. Monitor for reduced efficacy. Consider alternative.",
        "moderate", "CPIC:CYP2D6:codeine:2023", "2023.1", "PMID:32722396", "actionable",
    ),
    CPICRecommendation(
        "CYP2D6", "Ultrarapid Metabolizer", "codeine",
        "Avoid codeine. Risk of toxicity due to rapid morphine formation.",
        "strong", "CPIC:CYP2D6:codeine:2023", "2023.1", "PMID:32722396", "actionable",
    ),
    CPICRecommendation(
        "CYP2D6", "Normal Metabolizer", "codeine",
        "Use codeine per standard dosing guidelines.",
        "strong", "CPIC:CYP2D6:codeine:2023", "2023.1", "PMID:32722396", "informative",
    ),
    CPICRecommendation(
        "CYP2D6", "Poor Metabolizer", "tamoxifen",
        "Avoid tamoxifen. Consider aromatase inhibitor or alternative endocrine therapy.",
        "strong", "CPIC:CYP2D6:tamoxifen:2018", "2018.1", "PMID:29385237", "actionable",
    ),
    CPICRecommendation(
        "CYP2D6", "Intermediate Metabolizer", "tamoxifen",
        "Consider higher dose tamoxifen (40mg) or alternative endocrine therapy.",
        "moderate", "CPIC:CYP2D6:tamoxifen:2018", "2018.1", "PMID:29385237", "actionable",
    ),
]

# --- CYP2C19 Guidelines (CPIC 2022) ---

CYP2C19_GUIDELINES: list[CPICRecommendation] = [
    CPICRecommendation(
        "CYP2C19", "Poor Metabolizer", "clopidogrel",
        "Use alternative antiplatelet agent (prasugrel or ticagrelor) if no contraindication.",
        "strong", "CPIC:CYP2C19:clopidogrel:2022", "2022.1", "PMID:34032273", "actionable",
    ),
    CPICRecommendation(
        "CYP2C19", "Intermediate Metabolizer", "clopidogrel",
        "Use alternative antiplatelet agent (prasugrel or ticagrelor) if no contraindication.",
        "moderate", "CPIC:CYP2C19:clopidogrel:2022", "2022.1", "PMID:34032273", "actionable",
    ),
    CPICRecommendation(
        "CYP2C19", "Normal Metabolizer", "clopidogrel",
        "Use clopidogrel per standard dosing.",
        "strong", "CPIC:CYP2C19:clopidogrel:2022", "2022.1", "PMID:34032273", "informative",
    ),
    CPICRecommendation(
        "CYP2C19", "Rapid Metabolizer", "clopidogrel",
        "Use clopidogrel per standard dosing.",
        "strong", "CPIC:CYP2C19:clopidogrel:2022", "2022.1", "PMID:34032273", "informative",
    ),
    CPICRecommendation(
        "CYP2C19", "Ultrarapid Metabolizer", "clopidogrel",
        "Use clopidogrel per standard dosing.",
        "strong", "CPIC:CYP2C19:clopidogrel:2022", "2022.1", "PMID:34032273", "informative",
    ),
]

# --- HLA-B Guidelines (CPIC 2014/2023) ---

HLA_B_GUIDELINES: list[CPICRecommendation] = [
    CPICRecommendation(
        "HLA-B", "HLA-B*15:02 positive", "carbamazepine",
        "Do NOT use carbamazepine. High risk of Stevens-Johnson syndrome/toxic epidermal necrolysis.",
        "strong", "CPIC:HLA-B:carbamazepine:2014", "2014.1", "PMID:24407187", "actionable",
    ),
    CPICRecommendation(
        "HLA-B", "HLA-B*15:02 negative", "carbamazepine",
        "Use carbamazepine per standard dosing. Low risk of SJS/TEN from HLA-B*15:02.",
        "strong", "CPIC:HLA-B:carbamazepine:2014", "2014.1", "PMID:24407187", "informative",
    ),
    CPICRecommendation(
        "HLA-B", "HLA-B*15:02 positive", "oxcarbazepine",
        "Do NOT use oxcarbazepine. High risk of SJS/TEN.",
        "strong", "CPIC:HLA-B:oxcarbazepine:2014", "2014.1", "PMID:24407187", "actionable",
    ),
    CPICRecommendation(
        "HLA-B", "HLA-B*15:02 positive", "phenytoin",
        "Avoid phenytoin. Consider alternative anticonvulsant.",
        "moderate", "CPIC:HLA-B:phenytoin:2014", "2014.1", "PMID:24407187", "actionable",
    ),
]

ALL_GUIDELINES = CYP2D6_GUIDELINES + CYP2C19_GUIDELINES + HLA_B_GUIDELINES


def lookup_recommendation(gene: str, phenotype: str, drug: str) -> CPICRecommendation | None:
    """Deterministic lookup of CPIC recommendation by gene/phenotype/drug."""
    for rec in ALL_GUIDELINES:
        if rec.gene == gene and rec.phenotype == phenotype and rec.drug == drug:
            return rec
    return None


def get_guidelines_for_gene(gene: str) -> list[CPICRecommendation]:
    """Get all guidelines for a specific gene."""
    return [r for r in ALL_GUIDELINES if r.gene == gene]
