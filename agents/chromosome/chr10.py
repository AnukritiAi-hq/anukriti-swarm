"""Chromosome 10 Agent.

Pharmacogenomically relevant genes on chr10:
- CYP2C19: Clopidogrel, PPIs, antidepressants
- CYP2C9: Warfarin, NSAIDs, phenytoin

Future: Will handle CYP2C cluster haplotype phasing and
star allele assignment for the 2C subfamily.
"""

from agents.chromosome import BaseChromosomeAgent


class Chromosome10Agent(BaseChromosomeAgent):
    """Chromosome 10 specialist — CYP2C9/CYP2C19 cluster."""

    @property
    def chromosome(self) -> str:
        return "chr10"
