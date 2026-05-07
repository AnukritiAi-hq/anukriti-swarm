"""Anukriti Swarm — Population Agent Base.

Base class for population-specialized agents. Each population agent
provides allele frequency data for its population group using mock
data (future: MCP-based gnomAD lookups).
"""

from __future__ import annotations

from abc import abstractmethod

from agents.base import BaseAgent
from agents.models import AgentType, ExecutionMode, PopulationContext
from agents.state import SwarmState
from datasets.mock_data import MOCK_POPULATION_AFR, MOCK_POPULATION_EUR, MOCK_POPULATION_SAS

_POPULATION_DATA: dict[str, dict[str, PopulationContext]] = {
    "SAS": MOCK_POPULATION_SAS,
    "EUR": MOCK_POPULATION_EUR,
    "AFR": MOCK_POPULATION_AFR,
}


class BasePopulationAgent(BaseAgent):
    """Abstract base for population-specialized agents.

    Looks up allele frequencies from mock data keyed by population code.
    Returns PopulationContext entries for each target gene's key alleles.
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
        """Lookup allele frequencies for target genes in this population."""
        target_genes = state.get("target_genes", [])
        contexts = list(state.get("population_contexts", []))

        pop_data = _POPULATION_DATA.get(self.population_code, {})

        for gene in target_genes:
            # Look for any allele key containing this gene name
            for allele_key, ctx in pop_data.items():
                if gene in allele_key:
                    contexts.append(ctx)

        return {"population_contexts": contexts}  # type: ignore[return-value]
