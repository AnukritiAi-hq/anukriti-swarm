"""African (AFR) Population Agent.

Specialized for African pharmacogenomic context:
- Highest genetic diversity of any super-population
- Unique CYP2D6 allele distribution (high *17, *29 frequency)
- Population-specific dosage considerations

Future: Will integrate with AFR-specific frequency tables and
account for sub-population diversity within Africa.
"""

from agents.population import BasePopulationAgent


class AFRAgent(BasePopulationAgent):
    """African population agent.

    Handles allele frequency lookups and pharmacogenomic contextualization
    for African populations. Accounts for high genetic diversity.
    """

    @property
    def population_code(self) -> str:
        return "AFR"
