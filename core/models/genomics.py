"""Core genomic domain models.

Defines the fundamental genomic entities: variants, alleles, haplotypes,
and metabolizer phenotypes. These are the building blocks consumed by
all downstream agents.

Biomedical context:
- A variant is a single nucleotide change at a genomic position
- An allele (star allele) is a named haplotype defined by one or more variants
- A diplotype is the combination of two alleles (maternal + paternal)
- A phenotype is the functional consequence (e.g., metabolizer status)

Extensibility:
- Supports future multi-omics (add expression, methylation fields)
- Supports structural variants (CNV, gene deletions)
- Compatible with VCF 4.3+ and PharmVar nomenclature
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class OriginType(str, Enum):
    """Whether a data point was produced deterministically or generatively."""

    DETERMINISTIC = "deterministic"
    GENERATIVE = "generative"


class FunctionalImpact(str, Enum):
    """Predicted functional impact of a variant on gene product."""

    NO_FUNCTION = "no_function"
    DECREASED_FUNCTION = "decreased_function"
    NORMAL_FUNCTION = "normal_function"
    INCREASED_FUNCTION = "increased_function"
    UNCERTAIN = "uncertain"


class MetabolizerPhenotype(str, Enum):
    """Standardized metabolizer phenotype classifications (CPIC).

    These map directly to CPIC activity score ranges and determine
    drug dosing recommendations.
    """

    POOR = "Poor Metabolizer"
    INTERMEDIATE = "Intermediate Metabolizer"
    NORMAL = "Normal Metabolizer"
    RAPID = "Rapid Metabolizer"
    ULTRARAPID = "Ultrarapid Metabolizer"
    INDETERMINATE = "Indeterminate"


class GenomicVariant(BaseModel):
    """A single genomic variant (SNV/indel) from sequencing data.

    Represents one row from a VCF file with provenance metadata.
    Position uses 1-based coordinates on GRCh38.

    Future: Will support structural variants (CNV, inversions) via
    additional fields (sv_type, sv_length, copy_number).
    """

    chromosome: str = Field(..., description="Chromosome (e.g., 'chr22')")
    position: int = Field(..., gt=0, description="1-based genomic position (GRCh38)")
    ref_allele: str = Field(..., min_length=1, description="Reference allele")
    alt_allele: str = Field(..., min_length=1, description="Alternate allele")
    rsid: str | None = Field(None, description="dbSNP identifier (e.g., 'rs3892097')")
    gene: str | None = Field(None, description="Gene symbol (HGNC)")
    quality: float | None = Field(None, ge=0, description="Phred-scaled quality score")
    functional_impact: FunctionalImpact = FunctionalImpact.UNCERTAIN
    source: str = Field("VCF", description="Data source identifier")
    origin: OriginType = OriginType.DETERMINISTIC
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class StarAllele(BaseModel):
    """A pharmacogene star allele (named haplotype).

    Star alleles are the standard nomenclature for pharmacogene variants
    (e.g., CYP2D6*4). Defined by PharmVar as specific combinations of
    variants on a single chromosome copy.

    Future: Will link to PharmVar allele definition IDs and support
    suballele notation (e.g., *4.001, *4.002).
    """

    gene: str = Field(..., description="Gene symbol (e.g., 'CYP2D6')")
    allele_name: str = Field(..., description="Star allele name (e.g., '*4')")
    function: FunctionalImpact = FunctionalImpact.UNCERTAIN
    defining_variants: list[str] = Field(default_factory=list, description="rsIDs defining this allele")
    source: str = Field("PharmVar", description="Allele definition source")
    version: str | None = Field(None, description="Source database version")

    model_config = {"frozen": True}


class Diplotype(BaseModel):
    """A diplotype — the combination of two star alleles for a gene.

    Represents the patient's genotype at a pharmacogene locus.
    The two alleles are unordered (allele1/allele2 convention).

    Future: Will support phasing confidence and ambiguous calls.
    """

    gene: str
    allele1: StarAllele
    allele2: StarAllele
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Assignment confidence")
    source: str = Field("PharmVar", description="Assignment method/source")
    origin: OriginType = OriginType.DETERMINISTIC

    @property
    def display(self) -> str:
        """Human-readable diplotype string (e.g., '*1/*4')."""
        return f"{self.allele1.allele_name}/{self.allele2.allele_name}"


class Phenotype(BaseModel):
    """Metabolizer phenotype derived from a diplotype.

    The phenotype determines clinical actionability — it maps to
    specific dosing recommendations in CPIC/DPWG guidelines.

    Future: Will support activity score-based assignment and
    phenotype modifiers (e.g., inhibitor co-administration).
    """

    gene: str
    diplotype_display: str = Field(..., description="e.g., '*1/*4'")
    phenotype: MetabolizerPhenotype
    activity_score: float | None = Field(None, ge=0.0, description="CPIC activity score")
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    guideline_source: str | None = Field(None, description="e.g., 'CPIC:CYP2D6:2023'")
    origin: OriginType = OriginType.DETERMINISTIC
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
