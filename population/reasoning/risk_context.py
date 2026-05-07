"""Population-specific risk context and sparse-data warnings.

Generates contextual risk assessments that explain what a finding
means in the context of a specific population. Also flags when
data is insufficient for confident interpretation.

Key principle: The same genotype has different risk implications
depending on population prevalence. A rare genotype in a population
warrants more attention than a common one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from population.data.frequency_store import FrequencyStore


@dataclass(frozen=True)
class SparseDataWarning:
    """Warning when population data is insufficient for confident reasoning."""

    gene: str
    population: str
    reason: str
    severity: str  # "low", "medium", "high"
    recommendation: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class RiskContext:
    """Population-specific risk context for a pharmacogenomic finding."""

    gene: str
    allele: str
    population: str
    frequency: float | None
    rarity_class: str       # "common", "low_frequency", "rare", "very_rare", "absent"
    clinical_note: str      # Population-contextualized interpretation
    confidence: float
    warnings: list[SparseDataWarning] = field(default_factory=list)
    source: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# Rarity classification thresholds
_RARITY_THRESHOLDS = [
    (0.05, "common"),           # ≥ 5%
    (0.01, "low_frequency"),    # 1-5%
    (0.001, "rare"),            # 0.1-1%
    (0.0001, "very_rare"),      # 0.01-0.1%
]


def classify_rarity(frequency: float | None) -> str:
    """Classify allele rarity based on frequency."""
    if frequency is None:
        return "absent"
    for threshold, label in _RARITY_THRESHOLDS:
        if frequency >= threshold:
            return label
    return "very_rare"


def generate_risk_context(
    store: FrequencyStore, gene: str, allele: str, population: str
) -> RiskContext:
    """Generate population-specific risk context for an allele.

    Provides a contextualized interpretation of what this allele means
    in the given population, including rarity classification and
    clinical notes.
    """
    result = store.lookup(gene, allele, population)
    warnings: list[SparseDataWarning] = []

    if not result.found:
        warnings.append(SparseDataWarning(
            gene=gene, population=population,
            reason=f"No frequency data for {gene} {allele} in {population}",
            severity="high",
            recommendation="Interpret with caution. Consider using closest reference population.",
        ))
        return RiskContext(
            gene=gene, allele=allele, population=population,
            frequency=None, rarity_class="absent",
            clinical_note=f"No data available for {gene} {allele} in {population}. Cannot assess population-specific risk.",
            confidence=0.2, warnings=warnings, source="not_found",
        )

    # Check for sparse data
    if result.sample_n and result.sample_n < 1000:
        warnings.append(SparseDataWarning(
            gene=gene, population=population,
            reason=f"Small sample size (n={result.sample_n}) for {population}",
            severity="medium",
            recommendation="Frequency estimate may be imprecise. Larger studies needed.",
        ))

    rarity = classify_rarity(result.frequency)
    confidence = 0.95 if (result.sample_n and result.sample_n >= 10000) else 0.75
    note = _generate_clinical_note(gene, allele, population, result.frequency, rarity)

    return RiskContext(
        gene=gene, allele=allele, population=population,
        frequency=result.frequency, rarity_class=rarity,
        clinical_note=note, confidence=confidence,
        warnings=warnings, source=result.source,
    )


def check_sparse_data(store: FrequencyStore, gene: str, population: str) -> list[SparseDataWarning]:
    """Check for sparse data issues for a gene in a population."""
    profile = store.get_population_profile(gene, population)
    warnings: list[SparseDataWarning] = []

    if not profile:
        warnings.append(SparseDataWarning(
            gene=gene, population=population,
            reason=f"No frequency data available for {gene} in {population}",
            severity="high",
            recommendation="Population-specific interpretation not possible.",
        ))
        return warnings

    min_n = min((r.sample_n for r in profile if r.sample_n), default=0)
    if min_n < 500:
        warnings.append(SparseDataWarning(
            gene=gene, population=population,
            reason=f"Underrepresented population: minimum sample size n={min_n}",
            severity="medium",
            recommendation="Results may not generalize. Prioritize population-specific studies.",
        ))

    return warnings


def _generate_clinical_note(
    gene: str, allele: str, population: str, frequency: float | None, rarity: str
) -> str:
    """Generate a population-contextualized clinical note."""
    if frequency is None:
        return f"{gene} {allele} has no frequency data in {population}."

    freq_pct = f"{frequency:.1%}"

    if rarity == "common":
        return (
            f"{gene} {allele} is common in {population} ({freq_pct}). "
            f"This is an expected finding and well-characterized in this population."
        )
    if rarity == "low_frequency":
        return (
            f"{gene} {allele} is at low frequency in {population} ({freq_pct}). "
            f"Less common but well-documented. Standard guidelines apply."
        )
    if rarity == "rare":
        return (
            f"{gene} {allele} is rare in {population} ({freq_pct}). "
            f"Unusual finding for this population. Verify genotyping accuracy."
        )
    return (
        f"{gene} {allele} is very rare in {population} ({freq_pct}). "
        f"Unexpected finding. Consider genotyping error or admixed ancestry."
    )
