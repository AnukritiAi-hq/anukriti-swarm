"""Deterministic phenotype inference rules.

Pure rule-based phenotype assignment using CPIC activity score system.
No LLM dependency — these rules are authoritative and reproducible.

Activity Score System (CPIC):
- Each allele has a function value → activity score
- Diplotype activity score = sum of two allele scores
- Activity score maps to phenotype via defined ranges

Future extensibility:
- Polygenic scoring (add modifier genes)
- Pathway reasoning (multi-gene interactions)
- Multi-omics integration (expression modifiers)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


# --- Allele Function → Activity Score ---

ALLELE_ACTIVITY_SCORES: dict[str, dict[str, float]] = {
    "CYP2D6": {
        "*1": 1.0, "*2": 1.0,          # Normal function
        "*4": 0.0, "*5": 0.0,          # No function
        "*10": 0.5, "*17": 0.5, "*41": 0.5,  # Decreased function
        "*1xN": 2.0, "*2xN": 2.0,      # Increased function (gene duplication)
    },
    "CYP2C19": {
        "*1": 1.0,                      # Normal function
        "*2": 0.0, "*3": 0.0,          # No function
        "*17": 1.5,                     # Increased function
    },
}

# --- Activity Score → Phenotype Mapping ---

PHENOTYPE_RANGES: dict[str, list[tuple[float, float, str]]] = {
    "CYP2D6": [
        (0.0, 0.0, "Poor Metabolizer"),
        (0.25, 1.0, "Intermediate Metabolizer"),
        (1.25, 2.25, "Normal Metabolizer"),
        (2.5, 2.5, "Rapid Metabolizer"),      # Not standard for CYP2D6
        (3.0, 4.0, "Ultrarapid Metabolizer"),
    ],
    "CYP2C19": [
        (0.0, 0.0, "Poor Metabolizer"),
        (0.5, 1.0, "Intermediate Metabolizer"),
        (1.5, 2.0, "Normal Metabolizer"),
        (2.5, 2.5, "Rapid Metabolizer"),
        (3.0, 3.0, "Ultrarapid Metabolizer"),
    ],
}


@dataclass(frozen=True)
class PhenotypeInference:
    """Result of deterministic phenotype inference."""

    gene: str
    allele1: str
    allele2: str
    diplotype: str
    activity_score: float
    phenotype: str
    confidence: float
    rule_version: str
    source: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def get_activity_score(gene: str, allele: str) -> float | None:
    """Get activity score for a single allele. Returns None if unknown."""
    return ALLELE_ACTIVITY_SCORES.get(gene, {}).get(allele)


def infer_phenotype(gene: str, allele1: str, allele2: str) -> PhenotypeInference:
    """Deterministic phenotype inference from diplotype.

    Uses CPIC activity score system:
    1. Look up activity score for each allele
    2. Sum scores for diplotype activity score
    3. Map to phenotype via defined ranges

    Returns PhenotypeInference with full provenance.
    """
    score1 = get_activity_score(gene, allele1)
    score2 = get_activity_score(gene, allele2)

    # Handle unknown alleles
    if score1 is None or score2 is None:
        unknown = allele1 if score1 is None else allele2
        return PhenotypeInference(
            gene=gene, allele1=allele1, allele2=allele2,
            diplotype=f"{allele1}/{allele2}",
            activity_score=-1.0,
            phenotype="Indeterminate",
            confidence=0.0,
            rule_version="cpic_activity_score_v1",
            source=f"Unknown allele: {unknown}",
        )

    total_score = score1 + score2
    phenotype = _score_to_phenotype(gene, total_score)
    confidence = 1.0 if phenotype != "Indeterminate" else 0.5

    return PhenotypeInference(
        gene=gene, allele1=allele1, allele2=allele2,
        diplotype=f"{allele1}/{allele2}",
        activity_score=total_score,
        phenotype=phenotype,
        confidence=confidence,
        rule_version="cpic_activity_score_v1",
        source="CPIC_activity_score_system",
    )


def _score_to_phenotype(gene: str, score: float) -> str:
    """Map activity score to phenotype using gene-specific ranges."""
    ranges = PHENOTYPE_RANGES.get(gene, [])
    for low, high, phenotype in ranges:
        if low <= score <= high:
            return phenotype
    # Fallback for scores between defined ranges
    if score > 0 and score < 1.25:
        return "Intermediate Metabolizer"
    if score >= 1.25:
        return "Normal Metabolizer"
    return "Indeterminate"
