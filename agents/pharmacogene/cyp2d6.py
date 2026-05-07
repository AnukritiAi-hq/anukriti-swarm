"""CYP2D6 specialist agent.

The most complex pharmacogene — metabolizes ~25% of clinically used drugs.
Key drugs: codeine, tamoxifen, tramadol, amitriptyline, antipsychotics.

Complexity factors:
- Gene deletions (*5) and duplications (*1xN, *2xN)
- Hybrid alleles (CYP2D6/CYP2D7)
- High allele diversity (>100 star alleles defined)
- Population-specific allele distributions

Risk classification:
- PM: high risk (codeine inefficacy, tamoxifen failure)
- UM: high risk (codeine toxicity — rapid morphine formation)
- IM: moderate risk (reduced efficacy for prodrugs)
- NM: standard
"""

from __future__ import annotations

from agents.pharmacogene.base import BasePharmacogeneAgent


class CYP2D6Agent(BasePharmacogeneAgent):
    """CYP2D6 specialist — most complex pharmacogene."""

    @property
    def gene(self) -> str:
        return "CYP2D6"

    @property
    def drugs(self) -> list[str]:
        return ["codeine", "tamoxifen"]

    def _classify_risk(self, phenotype: str) -> str:
        if phenotype in ("Poor Metabolizer", "Ultrarapid Metabolizer"):
            return "high_risk"
        if phenotype == "Intermediate Metabolizer":
            return "moderate_risk"
        if phenotype == "Normal Metabolizer":
            return "standard"
        return "indeterminate"
