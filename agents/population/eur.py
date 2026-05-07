"""European (EUR) Population Agent.

Specialized for European pharmacogenomic context:
- Most extensively studied population in pharmacogenomics
- Well-characterized CYP2D6 *4 (most common no-function allele)
- CPIC guidelines primarily validated in EUR populations

Future: Will integrate with EUR-specific frequency tables and
flag when guidelines may have EUR-centric bias.
"""

from agents.population import BasePopulationAgent


class EURAgent(BasePopulationAgent):
    """European population agent.

    Handles allele frequency lookups and pharmacogenomic contextualization
    for European populations. Notes EUR-centric bias in existing guidelines.
    """

    @property
    def population_code(self) -> str:
        return "EUR"
