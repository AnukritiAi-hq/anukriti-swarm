"""Pharmacogenomic reasoning models.

Defines drug-gene interactions, dosing recommendations, evidence citations,
and retrieval results. These models represent the output of pharmacogene
agents and the evidence that grounds their conclusions.

Biomedical context:
- A recommendation maps a phenotype to a clinical action (dose change, alternative drug)
- Evidence citations link to CPIC/DPWG guidelines or PubMed literature
- Retrieval results are ranked passages from vector search

Extensibility:
- Supports multiple guideline sources (CPIC, DPWG, RNPGx, CPNDS)
- Evidence model supports future knowledge graph integration
- Recommendation strength levels align with CPIC classification
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from core.models.genomics import MetabolizerPhenotype, OriginType


class EvidenceLevel(str, Enum):
    """Strength of evidence supporting a recommendation (CPIC levels)."""

    STRONG = "strong"          # Level A — prescribing action recommended
    MODERATE = "moderate"      # Level B — prescribing action recommended
    OPTIONAL = "optional"      # Level C — informational, optional action
    INFORMATIVE = "informative"  # Level D — informational only


class GuidelineSource(str, Enum):
    """Pharmacogenomic guideline organizations."""

    CPIC = "CPIC"
    DPWG = "DPWG"
    PHARMGKB = "PharmGKB"
    FDA = "FDA"


class EvidenceCitation(BaseModel):
    """A citation linking a claim to its source.

    Every pharmacogenomic claim must be traceable to a specific source.
    Citations can reference guidelines, papers, or database entries.

    Future: Will support DOI resolution, citation graph traversal,
    and automatic staleness detection (source version tracking).
    """

    source_id: str = Field(..., description="e.g., 'PMID:32722396' or 'CPIC:CYP2D6:2023'")
    title: str | None = None
    url: str | None = None
    guideline_source: GuidelineSource | None = None
    year: int | None = Field(None, ge=1990, le=2030)
    evidence_level: EvidenceLevel = EvidenceLevel.INFORMATIVE
    accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class DrugGeneInteraction(BaseModel):
    """A known drug-gene interaction from pharmacogenomic databases.

    Represents the relationship between a specific gene phenotype
    and a drug's efficacy, toxicity, or dosing requirement.

    Future: Will support interaction severity scoring, polypharmacy
    interactions, and drug-drug-gene three-way interactions.
    """

    gene: str = Field(..., description="Gene symbol (e.g., 'CYP2D6')")
    drug: str = Field(..., description="Drug name (e.g., 'codeine')")
    phenotype: MetabolizerPhenotype
    interaction_type: str = Field(..., description="e.g., 'reduced_efficacy', 'increased_toxicity'")
    clinical_significance: EvidenceLevel = EvidenceLevel.INFORMATIVE
    citations: list[EvidenceCitation] = Field(default_factory=list)
    origin: OriginType = OriginType.DETERMINISTIC

    model_config = {"frozen": True}


class Recommendation(BaseModel):
    """A pharmacogenomic dosing recommendation.

    Maps a gene/phenotype/drug combination to a specific clinical action.
    Grounded in guideline citations with explicit evidence level.

    Future: Will support dose calculation, alternative drug ranking,
    and population-adjusted recommendations.
    """

    gene: str
    drug: str
    phenotype: MetabolizerPhenotype
    action: str = Field(..., description="Recommended action (e.g., 'Use alternative analgesic')")
    strength: EvidenceLevel = EvidenceLevel.INFORMATIVE
    guideline_source: GuidelineSource | None = None
    guideline_id: str | None = Field(None, description="e.g., 'CPIC:CYP2D6:codeine:2023'")
    citations: list[EvidenceCitation] = Field(default_factory=list)
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    origin: OriginType = OriginType.DETERMINISTIC
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RetrievalResult(BaseModel):
    """A passage retrieved from vector search or literature lookup.

    Ranked by relevance score. Used by retrieval agents to provide
    grounding context for generative agents.

    Future: Will support chunk-level provenance, embedding model version,
    and re-ranking scores from cross-encoder.
    """

    passage: str = Field(..., description="Retrieved text passage")
    source_id: str = Field(..., description="Source identifier (PMID, guideline ID)")
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    gene: str | None = None
    drug: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    retrieval_method: str = Field("vector_search", description="How this was retrieved")
    origin: OriginType = OriginType.DETERMINISTIC
