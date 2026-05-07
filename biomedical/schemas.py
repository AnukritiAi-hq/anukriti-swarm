"""Normalized biomedical data schemas.

Defines the canonical data structures for pharmacogenomic integration.
All external data (PharmFreq, CPIC, gnomAD, PharmGKB) is normalized
into these schemas before use by agents.

Future compatibility:
- PharmGKB clinical annotations
- gnomAD structural variants
- Local ancestry inference results
- Federated genomic dataset responses
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class DataSource(str, Enum):
    """Origin of biomedical data."""

    CPIC = "CPIC"
    PHARMFREQ = "PharmFreq"
    GNOMAD = "gnomAD"
    PHARMGKB = "PharmGKB"
    PHARMVAR = "PharmVar"
    CLINVAR = "ClinVar"
    FDA = "FDA"
    INTERNAL = "internal"


@dataclass(frozen=True)
class Provenance:
    """Data provenance metadata — attached to every data record."""

    source: DataSource
    version: str
    accessed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    license: str = "research_only"
    url: str | None = None


@dataclass(frozen=True)
class GeneRecord:
    """Normalized pharmacogene metadata."""

    symbol: str                     # HGNC symbol (e.g., "CYP2D6")
    chromosome: str                 # e.g., "chr22"
    function: str                   # e.g., "Drug metabolism"
    key_drugs: list[str] = field(default_factory=list)
    key_alleles: list[str] = field(default_factory=list)
    clinical_significance: str = ""
    provenance: Provenance | None = None


@dataclass(frozen=True)
class AlleleRecord:
    """Normalized star allele definition."""

    gene: str
    allele: str                     # e.g., "*4"
    function_status: str            # "no_function", "decreased_function", "normal_function", "increased_function"
    activity_score: float
    defining_variants: list[str] = field(default_factory=list)  # rsIDs
    clinical_significance: str = ""
    provenance: Provenance | None = None


@dataclass(frozen=True)
class FrequencyRecord:
    """Normalized population allele frequency."""

    gene: str
    allele: str
    population: str
    frequency: float
    sample_n: int
    confidence_interval: tuple[float, float] | None = None
    provenance: Provenance | None = None


@dataclass(frozen=True)
class GuidelineRecord:
    """Normalized clinical guideline recommendation."""

    gene: str
    drug: str
    phenotype: str
    recommendation: str
    strength: str                   # "strong", "moderate", "optional"
    classification: str             # "actionable", "informative"
    guideline_id: str
    pmid: str | None = None
    provenance: Provenance | None = None


@dataclass(frozen=True)
class PrevalenceRecord:
    """Population-level phenotype prevalence."""

    gene: str
    population: str
    phenotype: str                  # "PM", "IM", "NM", "RM", "UM"
    prevalence: float               # 0.0 - 1.0
    sample_n: int
    method: str = "hardy_weinberg"
    provenance: Provenance | None = None
