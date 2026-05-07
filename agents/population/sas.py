"""South Asian (SAS) Population Agent.

Specialized for South Asian pharmacogenomic context:
- Allele frequencies from gnomAD SAS subset
- Population-specific CYP2D6, CYP2C19 considerations
- High prevalence of certain star alleles in SAS populations

Future: Will integrate with SAS-specific frequency tables and
ethnopharmacogenomic literature for this population.
"""

from agents.population import BasePopulationAgent


class SASAgent(BasePopulationAgent):
    """South Asian population agent.

    Handles allele frequency lookups and pharmacogenomic contextualization
    for South Asian populations (Indian, Pakistani, Bangladeshi, Sri Lankan).
    """

    @property
    def population_code(self) -> str:
        return "SAS"
