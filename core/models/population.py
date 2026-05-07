"""Population and ancestry domain models.

Defines population context, allele frequency data, and ancestry
classification used by population agents for contextualized reasoning.

Biomedical context:
- Super-populations (AFR, AMR, EAS, EUR, SAS) from 1000 Genomes/gnomAD
- Allele frequencies vary dramatically across populations
- Population context is critical for interpreting pharmacogenomic results
- A "common" allele in one population may be rare in another

Extensibility:
- Supports sub-population granularity (e.g., SAS → GIH, ITU, PJL)
- Supports admixture and multi-ancestry individuals
- Compatible with future federated population databases
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from core.models.genomics import OriginType


class SuperPopulation(str, Enum):
    """1000 Genomes / gnomAD super-population codes."""

    AFR = "AFR"  # African
    AMR = "AMR"  # Admixed American
    EAS = "EAS"  # East Asian
    EUR = "EUR"  # European
    SAS = "SAS"  # South Asian


class AncestrySource(str, Enum):
    """How ancestry was determined."""

    SELF_REPORTED = "self_reported"
    INFERRED_PCA = "inferred_pca"       # Principal component analysis
    INFERRED_ADMIXTURE = "inferred_admixture"
    REFERENCE_PANEL = "reference_panel"


class AlleleFrequency(BaseModel):
    """Population-specific allele frequency for a variant or star allele.

    Frequencies are essential for interpreting whether a finding is
    expected or unusual in the patient's population context.

    Future: Will support sub-population frequencies, confidence intervals,
    and sample size metadata for statistical power assessment.
    """

    allele: str = Field(..., description="Allele identifier (e.g., 'CYP2D6*4', 'rs3892097-T')")
    population: SuperPopulation
    frequency: float = Field(..., ge=0.0, le=1.0, description="Minor allele frequency")
    sample_count: int | None = Field(None, ge=0, description="Number of samples in reference")
    source: str = Field("gnomAD", description="Frequency database")
    version: str | None = Field(None, description="Database version (e.g., 'v4.0')")
    is_common: bool = Field(False, description="Frequency > 0.01 in this population")
    origin: OriginType = OriginType.DETERMINISTIC
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class AncestryAssignment(BaseModel):
    """Ancestry classification for a sample.

    Determines which population agent handles the analysis and which
    frequency tables are used for contextualization.

    Future: Will support multi-ancestry (admixed) individuals with
    proportional ancestry components and confidence per component.
    """

    primary_population: SuperPopulation
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    method: AncestrySource = AncestrySource.SELF_REPORTED
    secondary_populations: list[SuperPopulation] = Field(default_factory=list)
    admixture_proportions: dict[str, float] = Field(
        default_factory=dict, description="Population → proportion (sums to 1.0)"
    )
    origin: OriginType = OriginType.DETERMINISTIC


class PopulationContext(BaseModel):
    """Complete population context for a pharmacogenomic analysis.

    Aggregates ancestry assignment with relevant allele frequencies
    to provide full population-aware reasoning context.

    Future: Will support population-specific drug response data,
    pharmacoepidemiologic context, and health disparity annotations.
    """

    ancestry: AncestryAssignment
    allele_frequencies: list[AlleleFrequency] = Field(default_factory=list)
    population_notes: list[str] = Field(
        default_factory=list, description="Population-specific considerations"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
