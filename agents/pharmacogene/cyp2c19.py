"""CYP2C19 specialist agent.

Critical for antiplatelet therapy (clopidogrel) and PPIs.
High clinical impact: PM/IM patients on clopidogrel have increased
cardiovascular event risk due to reduced platelet inhibition.

Key population note:
- CYP2C19*2 is very common in SAS (~36%) and EAS (~30%)
- This means IM/PM phenotypes are highly prevalent in these populations
- Clopidogrel resistance is a major clinical concern in South/East Asia

Risk classification:
- PM: high risk (clopidogrel failure → cardiovascular events)
- IM: high risk (reduced clopidogrel activation)
- NM/RM/UM: standard (clopidogrel effective)
"""

from __future__ import annotations

from agents.pharmacogene.base import BasePharmacogeneAgent


class CYP2C19Agent(BasePharmacogeneAgent):
    """CYP2C19 specialist — critical for antiplatelet therapy."""

    @property
    def gene(self) -> str:
        return "CYP2C19"

    @property
    def drugs(self) -> list[str]:
        return ["clopidogrel"]

    def _classify_risk(self, phenotype: str) -> str:
        if phenotype == "Poor Metabolizer":
            return "high_risk"
        if phenotype == "Intermediate Metabolizer":
            return "high_risk"  # Both PM and IM are high risk for clopidogrel
        if phenotype in ("Normal Metabolizer", "Rapid Metabolizer", "Ultrarapid Metabolizer"):
            return "standard"
        return "indeterminate"
