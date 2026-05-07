"""Metabolizer prevalence estimation and confidence weighting.

Estimates the prevalence of metabolizer phenotypes in a population
using Hardy-Weinberg equilibrium from allele frequencies.

Key insight: The same diplotype (*1/*4) has very different clinical
significance depending on population context. In EUR (where *4 is common),
it's expected. In EAS (where *4 is rare), it warrants closer investigation.

Confidence weighting: Larger sample sizes → higher confidence.
Sparse data (small sample_n) triggers reduced confidence scores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from population.data.frequency_store import FrequencyLookupResult, FrequencyStore


@dataclass(frozen=True)
class PrevalenceEstimate:
    """Estimated prevalence of a metabolizer phenotype in a population."""

    gene: str
    population: str
    phenotype: str          # "PM", "IM", "NM", "RM", "UM"
    prevalence: float       # Estimated fraction (0.0 - 1.0)
    confidence: float       # Confidence in estimate (0.0 - 1.0)
    method: str             # "hardy_weinberg" or "direct_observation"
    sample_n: int           # Minimum sample size used
    source: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# Activity score mappings for CPIC phenotype assignment
_FUNCTION_SCORES = {
    "no_function": 0.0,
    "decreased_function": 0.5,
    "normal_function": 1.0,
    "increased_function": 1.5,
}

_PHENOTYPE_RANGES = {
    "PM": (0.0, 0.0),      # Activity score = 0
    "IM": (0.0, 1.0),      # 0 < score < 1.0 (exclusive bounds for IM)
    "NM": (1.0, 2.0),      # 1.0 ≤ score ≤ 2.0
    "RM": (2.0, 2.5),      # 2.0 < score ≤ 2.5
    "UM": (2.5, 3.0),      # score > 2.5
}


def estimate_phenotype_prevalence(
    store: FrequencyStore, gene: str, population: str
) -> list[PrevalenceEstimate]:
    """Estimate metabolizer phenotype prevalences using Hardy-Weinberg.

    Computes diplotype frequencies from allele frequencies (p² + 2pq + q²),
    then maps diplotypes to phenotypes via CPIC activity scores.

    Returns one PrevalenceEstimate per phenotype category.
    """
    profile = store.get_population_profile(gene, population)
    if not profile:
        return []

    # Build allele frequency map
    allele_freqs: dict[str, tuple[float, str]] = {}  # allele → (freq, function)
    min_sample_n = float("inf")
    source = ""

    for rec in profile:
        if rec.frequency is not None:
            allele_freqs[rec.allele] = (rec.frequency, rec.function or "normal_function")
            if rec.sample_n and rec.sample_n < min_sample_n:
                min_sample_n = rec.sample_n
            source = rec.source

    if not allele_freqs:
        return []

    # Compute diplotype frequencies and phenotype prevalences
    phenotype_prev: dict[str, float] = {"PM": 0.0, "IM": 0.0, "NM": 0.0, "RM": 0.0, "UM": 0.0}
    alleles = list(allele_freqs.keys())

    for i, a1 in enumerate(alleles):
        for j, a2 in enumerate(alleles):
            freq1, func1 = allele_freqs[a1]
            freq2, func2 = allele_freqs[a2]

            # Diplotype frequency (Hardy-Weinberg)
            if i == j:
                dip_freq = freq1 * freq2  # homozygous
            else:
                dip_freq = freq1 * freq2  # heterozygous (counted once per ordered pair)

            # Activity score
            score = _FUNCTION_SCORES.get(func1, 1.0) + _FUNCTION_SCORES.get(func2, 1.0)

            # Assign phenotype
            if score == 0.0:
                phenotype_prev["PM"] += dip_freq
            elif score < 1.0:
                phenotype_prev["IM"] += dip_freq
            elif score <= 2.0:
                phenotype_prev["NM"] += dip_freq
            elif score <= 2.5:
                phenotype_prev["RM"] += dip_freq
            else:
                phenotype_prev["UM"] += dip_freq

    # Confidence based on sample size
    confidence = _compute_confidence(int(min_sample_n) if min_sample_n != float("inf") else 0)

    return [
        PrevalenceEstimate(
            gene=gene, population=population, phenotype=pheno,
            prevalence=round(prev, 4), confidence=confidence,
            method="hardy_weinberg", sample_n=int(min_sample_n) if min_sample_n != float("inf") else 0,
            source=source,
        )
        for pheno, prev in phenotype_prev.items()
        if prev > 0.001  # Only report non-negligible prevalences
    ]


def _compute_confidence(sample_n: int) -> float:
    """Compute confidence score based on sample size.

    Thresholds:
    - n >= 10000: high confidence (0.95)
    - n >= 1000: moderate confidence (0.80)
    - n >= 100: low confidence (0.60)
    - n < 100: very low confidence (0.30)
    """
    if sample_n >= 10000:
        return 0.95
    if sample_n >= 1000:
        return 0.80
    if sample_n >= 100:
        return 0.60
    return 0.30
