"""Anukriti Swarm — Population Agent Base.

Base class for population-specialized agents. Each population agent
handles allele frequency lookups and population-specific pharmacogenomic
contextualization for a single super-population group.

Future responsibilities:
- MCP-based gnomAD/1000 Genomes frequency lookups
- Population-specific drug response patterns
- Ancestry inference from variant profiles
- Cross-population frequency comparison
"""

from __future__ import annotations

from abc import abstractmethod

from agents.base import BaseAgent
from agents.models import AgentType, ExecutionMode, PopulationContext
from agents.state import SwarmState


class BasePopulationAgent(BaseAgent):
    """Abstract base for population-specialized agents.

    Each subclass represents a single super-population (SAS, AFR, EUR, etc.)
    and provides population-specific allele frequency data and context.

    Execution is DETERMINISTIC for frequency lookups. Future generative
    capabilities (ancestry inference) will be clearly separated.
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.POPULATION

    @property
    def execution_mode(self) -> ExecutionMode:
        return ExecutionMode.DETERMINISTIC

    @property
    @abstractmethod
    def population_code(self) -> str:
        """3-letter super-population code (e.g., 'SAS', 'AFR', 'EUR')."""
        ...

    def execute(self, state: SwarmState) -> SwarmState:
        """Lookup allele frequencies for target genes in this population.

        Current: Returns placeholder population context.
        Future: Will query gnomAD via MCP Dataset server for real frequencies.
        """
        target_genes = state.get("target_genes", [])
        contexts = list(state.get("population_contexts", []))

        for gene in target_genes:
            contexts.append(self._lookup_frequency(gene))

        return {"population_contexts": contexts}  # type: ignore[return-value]

    def _lookup_frequency(self, gene: str) -> PopulationContext:
        """Lookup allele frequency for a gene in this population.

        Current: Returns placeholder.
        Future: MCP call to Dataset server → gnomAD frequency tables.
        """
        return PopulationContext(
            population=self.population_code,
            allele_frequency=None,  # Placeholder — no real data yet
            frequency_source=None,
            is_common=None,
        )
