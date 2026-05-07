"""HLA-B*15:02 risk agent.

Unlike CYP enzymes (metabolizer phenotypes), HLA-B is an immune gene
where specific alleles confer risk of severe adverse drug reactions:
- HLA-B*15:02 + carbamazepine → Stevens-Johnson syndrome / TEN
- HLA-B*15:02 + oxcarbazepine → SJS/TEN
- HLA-B*15:02 + phenytoin → SJS/TEN (moderate evidence)

This is a binary risk model (positive/negative), not a metabolizer spectrum.

Population context:
- *15:02 is common in Southeast Asian populations (EAS: ~8%)
- Rare in EUR (<1%) and AFR (<1%)
- FDA mandates testing before carbamazepine in at-risk populations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from guidelines.cpic import CPICRecommendation, lookup_recommendation


@dataclass(frozen=True)
class HLABRiskAssessment:
    """Risk assessment result for HLA-B*15:02."""

    agent_id: str
    gene: str
    allele_status: str      # "positive" or "negative"
    risk_phenotype: str     # "HLA-B*15:02 positive" or "HLA-B*15:02 negative"
    risk_level: str         # "contraindicated", "standard"
    drugs_affected: list[str]
    recommendations: list[CPICRecommendation]
    confidence: float
    origin: str = "deterministic"
    provenance: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class HLABAgent:
    """HLA-B*15:02 specialist — immune-mediated ADR risk assessment.

    Binary risk model: presence of *15:02 allele determines whether
    carbamazepine/oxcarbazepine/phenytoin are contraindicated.
    """

    gene = "HLA-B"
    agent_id = "pharmacogene_hla_b"
    drugs = ["carbamazepine", "oxcarbazepine", "phenytoin"]

    def assess_risk(self, has_15_02: bool) -> HLABRiskAssessment:
        """Deterministic risk assessment based on HLA-B*15:02 status.

        Args:
            has_15_02: Whether the patient carries at least one HLA-B*15:02 allele.
        """
        status = "positive" if has_15_02 else "negative"
        phenotype = f"HLA-B*15:02 {status}"
        risk_level = "contraindicated" if has_15_02 else "standard"

        recommendations = []
        for drug in self.drugs:
            rec = lookup_recommendation(self.gene, phenotype, drug)
            if rec:
                recommendations.append(rec)

        return HLABRiskAssessment(
            agent_id=self.agent_id,
            gene=self.gene,
            allele_status=status,
            risk_phenotype=phenotype,
            risk_level=risk_level,
            drugs_affected=self.drugs if has_15_02 else [],
            recommendations=recommendations,
            confidence=1.0,
            provenance={
                "rule_engine": "hla_binary_risk_v1",
                "guideline_source": "CPIC",
                "origin": "deterministic",
            },
        )
