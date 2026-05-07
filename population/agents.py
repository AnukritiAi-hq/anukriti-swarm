"""Population agents with full reasoning interface.

Each population agent provides:
- Allele frequency lookups with provenance
- Metabolizer prevalence estimation
- Population-specific risk context
- Sparse-data warnings
- Ancestry-aware interpretation metadata

All outputs are deterministic and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from population.data.frequency_store import FrequencyLookupResult, FrequencyStore
from population.reasoning.prevalence import PrevalenceEstimate, estimate_phenotype_prevalence
from population.reasoning.risk_context import (
    RiskContext,
    SparseDataWarning,
    check_sparse_data,
    generate_risk_context,
)


@dataclass(frozen=True)
class PopulationReasoningResult:
    """Complete population reasoning output for a gene/allele query.

    Aggregates frequency data, risk context, prevalence estimates,
    and warnings into a single auditable result.
    """

    agent_id: str
    population: str
    gene: str
    allele: str
    frequency: FrequencyLookupResult
    risk_context: RiskContext
    prevalence_estimates: list[PrevalenceEstimate]
    warnings: list[SparseDataWarning]
    confidence: float
    origin: str = "deterministic"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BasePopulationReasoningAgent:
    """Base class for population-aware reasoning agents.

    Each subclass represents a specific population and provides
    the full reasoning interface: frequency lookup, prevalence
    estimation, risk context, and sparse-data detection.
    """

    population_code: str = ""
    population_name: str = ""

    def __init__(self) -> None:
        self.store = FrequencyStore()
        self.agent_id = f"population_{self.population_code.lower()}"

    def reason(self, gene: str, allele: str) -> PopulationReasoningResult:
        """Full population-aware reasoning for a gene/allele.

        Returns a complete, auditable reasoning result including:
        - Frequency lookup with provenance
        - Risk context with clinical note
        - Prevalence estimates for all phenotypes
        - Sparse-data warnings if applicable
        """
        frequency = self.store.lookup(gene, allele, self.population_code)
        risk = generate_risk_context(self.store, gene, allele, self.population_code)
        prevalence = estimate_phenotype_prevalence(self.store, gene, self.population_code)
        warnings = check_sparse_data(self.store, gene, self.population_code)

        # Aggregate confidence from risk context and frequency data
        confidence = risk.confidence

        return PopulationReasoningResult(
            agent_id=self.agent_id,
            population=self.population_code,
            gene=gene, allele=allele,
            frequency=frequency,
            risk_context=risk,
            prevalence_estimates=prevalence,
            warnings=warnings + list(risk.warnings),
            confidence=confidence,
        )

    def get_profile(self, gene: str) -> list[FrequencyLookupResult]:
        """Get complete allele frequency profile for a gene."""
        return self.store.get_population_profile(gene, self.population_code)


class SASPopulationAgent(BasePopulationReasoningAgent):
    """South Asian population reasoning agent.

    Key characteristics:
    - High CYP2C19*2 frequency (~36%) — clopidogrel resistance concern
    - Moderate CYP2D6*4 (~9%) and *41 (~12%)
    - Well-represented in gnomAD (n≈15k)
    """

    population_code = "SAS"
    population_name = "South Asian"


class AFRPopulationAgent(BasePopulationReasoningAgent):
    """African population reasoning agent.

    Key characteristics:
    - Highest genetic diversity of any super-population
    - High CYP2D6*17 frequency (~20%) — unique decreased-function allele
    - Low CYP2D6*4 (~2%) — EUR-common allele is rare here
    - Well-represented in gnomAD (n≈20k)
    """

    population_code = "AFR"
    population_name = "African"


class EURPopulationAgent(BasePopulationReasoningAgent):
    """European population reasoning agent.

    Key characteristics:
    - Most extensively studied population in pharmacogenomics
    - High CYP2D6*4 frequency (~22%) — most common no-function allele
    - High CYP2C19*17 (~22%) — gain-of-function, rapid metabolizer risk
    - Largest reference sample (n≈64k)
    - Guidelines may have EUR-centric bias
    """

    population_code = "EUR"
    population_name = "European"
