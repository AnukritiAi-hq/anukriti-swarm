"""Chromosome 6 Agent.

Pharmacogenomically relevant genes on chr6:
- HLA-B: Abacavir hypersensitivity (HLA-B*57:01)
- HLA-A: Carbamazepine hypersensitivity (HLA-A*31:01)
- TPMT: Thiopurine metabolism

Future: Will handle HLA typing and immune-mediated adverse drug reactions.
"""

from agents.chromosome import BaseChromosomeAgent


class Chromosome6Agent(BaseChromosomeAgent):
    """Chromosome 6 specialist — HLA region and immune pharmacogenes."""

    @property
    def chromosome(self) -> str:
        return "chr6"
