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

# --- DPYD Guidelines (CPIC 2017 + Nov 2018 update) ---
#
# Source: Amstutz U, Henricks LM, Offer SM, et al. CPIC Guideline for
# Dihydropyrimidine Dehydrogenase Genotype and Fluoropyrimidine Dosing:
# 2017 Update. Clin Pharmacol Ther. 2018;103(2):210-216.
# PMID: 29152729 / PMC5760397.
#
# Phenotype assignment per CPIC activity score (sum of two lowest variant scores):
#   AS 2.0       -> Normal Metabolizer
#   AS 1.0 / 1.5 -> Intermediate Metabolizer (BOTH get 50% reduction per Nov 2018 update)
#   AS 0.0 / 0.5 -> Poor Metabolizer
#
# CPIC pre-Nov-2018 split AS=1.0 (50% reduction) from AS=1.5 (25-50%).
# The Nov 2018 update collapsed both into a single 50% recommendation
# after Henricks 2018 (PMID: 30348537) showed AS=1.5 carriers given only
# 25% reduction still had increased toxicity. The recommendation text
# below mentions the homozygous c.[2846A>T];[2846A>T] (AS=1.0) caveat
# where >50% reduction may be warranted, per CPIC.
#
# Tegafur is intentionally NOT presented as an alternative — it is also
# DPD-metabolized, and DPWG explicitly flags this in the same guideline.
# Uridine triacetate (Vistogard, FDA-approved 2015) is the post-overdose
# rescue, mentioned here for clinical completeness but not as a dosing
# recommendation.

DPYD_GUIDELINES: list[CPICRecommendation] = [
    CPICRecommendation(
        "DPYD", "Normal Metabolizer", "fluorouracil",
        "Use 5-fluorouracil per standard dosing. Activity score 2; full DPD activity expected.",
        "strong", "CPIC:DPYD:fluoropyrimidines:2017", "2018.1", "PMID:29152729", "informative",
    ),
    CPICRecommendation(
        "DPYD", "Intermediate Metabolizer", "fluorouracil",
        "Reduce starting dose by 50% from the standard label dose, with subsequent dose "
        "titration based on toxicity and ideally therapeutic drug monitoring. Per CPIC Nov "
        "2018 update this applies to both activity score 1.0 and 1.5; for the homozygous "
        "c.[2846A>T];[2846A>T] genotype (AS=1.0) consider a >50% reduction. Tegafur is NOT a "
        "safe alternative (also DPD-metabolized).",
        "moderate", "CPIC:DPYD:fluoropyrimidines:2017", "2018.1", "PMID:29152729", "actionable",
    ),
    CPICRecommendation(
        "DPYD", "Poor Metabolizer", "fluorouracil",
        "Avoid 5-fluorouracil and prodrug-based regimens (capecitabine, tegafur). If no "
        "fluoropyrimidine-free alternative exists, administer at <25% of the standard dose "
        "with early therapeutic drug monitoring; phenotyping (DPD enzyme activity in "
        "peripheral mononuclear cells, or uracil/dihydrouracil ratio) is strongly "
        "recommended to refine the starting dose. Uridine triacetate (Vistogard) is the "
        "FDA-approved rescue if overdose occurs.",
        "strong", "CPIC:DPYD:fluoropyrimidines:2017", "2018.1", "PMID:29152729", "actionable",
    ),
    CPICRecommendation(
        # Same guidance for capecitabine — capecitabine is the oral prodrug
        # of 5-FU and CPIC ships identical recommendations. Adding a second
        # entry keyed on drug='capecitabine' lets the api expose either as
        # a workflow id without re-routing through fluorouracil.
        "DPYD", "Poor Metabolizer", "capecitabine",
        "Avoid capecitabine and other fluoropyrimidine prodrugs. If no fluoropyrimidine-free "
        "alternative exists, administer at <25% of standard dose with early therapeutic drug "
        "monitoring and phenotyping. Uridine triacetate (Vistogard) is the FDA-approved "
        "rescue for overdose.",
        "strong", "CPIC:DPYD:fluoropyrimidines:2017", "2018.1", "PMID:29152729", "actionable",
    ),
    CPICRecommendation(
        "DPYD", "Intermediate Metabolizer", "capecitabine",
        "Reduce starting dose by 50%, titrate by toxicity and ideally therapeutic drug "
        "monitoring. Per CPIC Nov 2018 update applies to AS=1.0 and AS=1.5; consider >50% "
        "reduction for homozygous c.[2846A>T];[2846A>T]. Tegafur is NOT a safe alternative.",
        "moderate", "CPIC:DPYD:fluoropyrimidines:2017", "2018.1", "PMID:29152729", "actionable",
    ),
    CPICRecommendation(
        "DPYD", "Normal Metabolizer", "capecitabine",
        "Use capecitabine per standard dosing. Activity score 2; full DPD activity expected.",
        "strong", "CPIC:DPYD:fluoropyrimidines:2017", "2018.1", "PMID:29152729", "informative",
    ),
]

ALL_GUIDELINES = (
    CYP2D6_GUIDELINES
    + CYP2C19_GUIDELINES
    + HLA_B_GUIDELINES
    + DPYD_GUIDELINES
)


def lookup_recommendation(gene: str, phenotype: str, drug: str) -> CPICRecommendation | None:
    """Deterministic lookup of CPIC recommendation by gene/phenotype/drug."""
    for rec in ALL_GUIDELINES:
        if rec.gene == gene and rec.phenotype == phenotype and rec.drug == drug:
            return rec
    return None


def get_guidelines_for_gene(gene: str) -> list[CPICRecommendation]:
    """Get all guidelines for a specific gene."""
    return [r for r in ALL_GUIDELINES if r.gene == gene]
