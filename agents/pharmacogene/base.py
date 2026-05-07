"""Base pharmacogene agent with deterministic reasoning API.

All pharmacogene specialist agents inherit from this base and implement
gene-specific analysis logic. The base provides:
- Standard reasoning interface (analyze_diplotype, get_recommendations)
- Provenance tracking on all outputs
- CPIC guideline integration
- Confidence scoring

Future extensibility hooks:
- polygenic_modifier(): adjust phenotype based on modifier genes
- pathway_context(): multi-gene pathway reasoning
- multi_omics_adjust(): expression/methylation modifiers
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from guidelines.cpic import CPICRecommendation, lookup_recommendation
from rules.phenotype_rules import PhenotypeInference, infer_phenotype


@dataclass(frozen=True)
class PharmacogeneAnalysis:
    """Complete analysis result from a pharmacogene specialist agent."""

    agent_id: str
    gene: str
    allele1: str
    allele2: str
    diplotype: str
    phenotype_inference: PhenotypeInference
    recommendations: list[CPICRecommendation]
    risk_classification: str  # "high_risk", "moderate_risk", "standard", "reduced_risk"
    confidence: float
    origin: str = "deterministic"
    provenance: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BasePharmacogeneAgent(ABC):
    """Abstract base for pharmacogene specialist agents.

    Provides deterministic reasoning API. Subclasses implement
    gene-specific logic (variant interpretation, risk classification).
    """

    @property
    @abstractmethod
    def gene(self) -> str:
        """Gene symbol this agent specializes in."""
        ...

    @property
    @abstractmethod
    def drugs(self) -> list[str]:
        """Drugs affected by this gene."""
        ...

    @property
    def agent_id(self) -> str:
        return f"pharmacogene_{self.gene.lower()}"

    def analyze_diplotype(self, allele1: str, allele2: str) -> PharmacogeneAnalysis:
        """Full deterministic analysis of a diplotype.

        Pipeline:
        1. Infer phenotype from diplotype (activity score rules)
        2. Look up CPIC recommendations for each affected drug
        3. Classify risk level
        4. Attach provenance metadata
        """
        inference = infer_phenotype(self.gene, allele1, allele2)
        recommendations = self._get_recommendations(inference.phenotype)
        risk = self._classify_risk(inference.phenotype)

        return PharmacogeneAnalysis(
            agent_id=self.agent_id,
            gene=self.gene,
            allele1=allele1, allele2=allele2,
            diplotype=inference.diplotype,
            phenotype_inference=inference,
            recommendations=recommendations,
            risk_classification=risk,
            confidence=inference.confidence,
            provenance={
                "rule_engine": inference.rule_version,
                "guideline_source": "CPIC",
                "origin": "deterministic",
            },
        )

    def _get_recommendations(self, phenotype: str) -> list[CPICRecommendation]:
        """Look up CPIC recommendations for this phenotype across all drugs."""
        recs = []
        for drug in self.drugs:
            rec = lookup_recommendation(self.gene, phenotype, drug)
            if rec:
                recs.append(rec)
        return recs

    @abstractmethod
    def _classify_risk(self, phenotype: str) -> str:
        """Gene-specific risk classification based on phenotype."""
        ...

    # --- Future extensibility hooks ---

    def polygenic_modifier(self, modifier_genes: dict[str, str]) -> float:
        """Adjust confidence based on modifier gene interactions (future)."""
        return 0.0  # No adjustment yet

    def pathway_context(self, pathway_genes: list[str]) -> dict[str, Any]:
        """Multi-gene pathway reasoning context (future)."""
        return {"status": "not_implemented", "pathway_genes": pathway_genes}

    def multi_omics_adjust(self, expression_level: float | None = None) -> float:
        """Expression/methylation-based phenotype adjustment (future)."""
        return 0.0  # No adjustment yet
