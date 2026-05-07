"""Population prevalence statistics with lookup API.

Realistic metabolizer phenotype prevalence data for SAS, AFR, EUR
derived from published pharmacogenomic studies and gnomAD frequencies.
"""

from __future__ import annotations

from biomedical.schemas import DataSource, PrevalenceRecord, Provenance

_GNOMAD = Provenance(source=DataSource.GNOMAD, version="v4.0")

# --- CYP2D6 Metabolizer Prevalence ---

CYP2D6_PREVALENCE: list[PrevalenceRecord] = [
    # South Asian
    PrevalenceRecord("CYP2D6", "SAS", "PM", 0.02, 15308, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2D6", "SAS", "IM", 0.28, 15308, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2D6", "SAS", "NM", 0.65, 15308, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2D6", "SAS", "UM", 0.05, 15308, "hardy_weinberg", _GNOMAD),
    # African
    PrevalenceRecord("CYP2D6", "AFR", "PM", 0.02, 20744, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2D6", "AFR", "IM", 0.30, 20744, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2D6", "AFR", "NM", 0.60, 20744, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2D6", "AFR", "UM", 0.08, 20744, "hardy_weinberg", _GNOMAD),
    # European
    PrevalenceRecord("CYP2D6", "EUR", "PM", 0.07, 64603, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2D6", "EUR", "IM", 0.25, 64603, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2D6", "EUR", "NM", 0.62, 64603, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2D6", "EUR", "UM", 0.06, 64603, "hardy_weinberg", _GNOMAD),
]

# --- CYP2C19 Metabolizer Prevalence ---

CYP2C19_PREVALENCE: list[PrevalenceRecord] = [
    # South Asian — high PM/IM due to *2 at 36%
    PrevalenceRecord("CYP2C19", "SAS", "PM", 0.14, 15308, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2C19", "SAS", "IM", 0.35, 15308, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2C19", "SAS", "NM", 0.38, 15308, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2C19", "SAS", "RM", 0.11, 15308, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2C19", "SAS", "UM", 0.02, 15308, "hardy_weinberg", _GNOMAD),
    # African
    PrevalenceRecord("CYP2C19", "AFR", "PM", 0.03, 20744, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2C19", "AFR", "IM", 0.18, 20744, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2C19", "AFR", "NM", 0.55, 20744, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2C19", "AFR", "RM", 0.20, 20744, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2C19", "AFR", "UM", 0.04, 20744, "hardy_weinberg", _GNOMAD),
    # European
    PrevalenceRecord("CYP2C19", "EUR", "PM", 0.02, 64603, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2C19", "EUR", "IM", 0.18, 64603, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2C19", "EUR", "NM", 0.40, 64603, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2C19", "EUR", "RM", 0.30, 64603, "hardy_weinberg", _GNOMAD),
    PrevalenceRecord("CYP2C19", "EUR", "UM", 0.10, 64603, "hardy_weinberg", _GNOMAD),
]

# --- HLA-B*15:02 Carrier Prevalence ---

HLA_B_PREVALENCE: list[PrevalenceRecord] = [
    PrevalenceRecord("HLA-B", "SAS", "carrier_15:02", 0.04, 15308, "direct_observation", _GNOMAD),
    PrevalenceRecord("HLA-B", "AFR", "carrier_15:02", 0.01, 20744, "direct_observation", _GNOMAD),
    PrevalenceRecord("HLA-B", "EUR", "carrier_15:02", 0.001, 64603, "direct_observation", _GNOMAD),
    PrevalenceRecord("HLA-B", "EAS", "carrier_15:02", 0.08, 9197, "direct_observation", _GNOMAD),
]

ALL_PREVALENCE = CYP2D6_PREVALENCE + CYP2C19_PREVALENCE + HLA_B_PREVALENCE


def get_prevalence(gene: str, population: str) -> list[PrevalenceRecord]:
    """Lookup prevalence records for a gene in a population."""
    return [r for r in ALL_PREVALENCE if r.gene == gene and r.population == population]


def get_phenotype_prevalence(gene: str, population: str, phenotype: str) -> PrevalenceRecord | None:
    """Lookup a specific phenotype prevalence."""
    for r in ALL_PREVALENCE:
        if r.gene == gene and r.population == population and r.phenotype == phenotype:
            return r
    return None
