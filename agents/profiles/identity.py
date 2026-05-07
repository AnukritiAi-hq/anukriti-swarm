"""Agent identity and specialization model.

Every agent in the swarm has a structured identity profile that describes:
- What it knows (expertise domain, supported genes/populations)
- What it can do (capabilities, reasoning scope)
- How confident it is (confidence profile, escalation thresholds)
- How to route to it (routing metadata)

This makes the swarm a federation of specialized genomic experts,
each with clear boundaries and introspectable capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AgentDomain(str, Enum):
    """Primary expertise domain of an agent."""

    ORCHESTRATION = "orchestration"
    POPULATION_GENOMICS = "population_genomics"
    PHARMACOGENOMICS = "pharmacogenomics"
    EVIDENCE_RETRIEVAL = "evidence_retrieval"
    VERIFICATION = "verification"
    NARRATIVE = "narrative"
    CHROMOSOME = "chromosome"       # Future
    PATHWAY = "pathway"             # Future
    MULTI_OMICS = "multi_omics"     # Future
    FEDERATED = "federated"         # Future


class ReasoningMode(str, Enum):
    """How the agent produces its outputs."""

    DETERMINISTIC = "deterministic"
    GENERATIVE = "generative"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class ConfidenceProfile:
    """Agent's confidence characteristics."""

    default_confidence: float = 1.0
    min_confidence_to_act: float = 0.7
    escalation_threshold: float = 0.5
    max_confidence: float = 1.0


@dataclass(frozen=True)
class AgentProfile:
    """Complete identity profile for a swarm agent.

    This is the agent's "business card" — it tells the orchestrator
    and other agents what this agent can do, what it knows about,
    and when to route queries to it.
    """

    # Identity
    agent_id: str
    name: str
    domain: AgentDomain
    reasoning_mode: ReasoningMode

    # Expertise
    description: str
    specialization: str
    supported_genes: list[str] = field(default_factory=list)
    supported_populations: list[str] = field(default_factory=list)
    supported_drugs: list[str] = field(default_factory=list)

    # Capabilities
    capabilities: list[str] = field(default_factory=list)
    reasoning_scope: str = ""

    # Confidence
    confidence_profile: ConfidenceProfile = field(default_factory=ConfidenceProfile)

    # Routing
    routing_keywords: list[str] = field(default_factory=list)
    priority: int = 5  # 0=highest, 9=lowest

    # Extensibility
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)

    def can_handle_gene(self, gene: str) -> bool:
        """Check if this agent handles a specific gene."""
        return not self.supported_genes or gene in self.supported_genes

    def can_handle_population(self, population: str) -> bool:
        """Check if this agent handles a specific population."""
        return not self.supported_populations or population in self.supported_populations

    def matches_query(self, gene: str | None = None, drug: str | None = None, population: str | None = None) -> bool:
        """Check if this agent is relevant for a query."""
        if gene and self.supported_genes and gene not in self.supported_genes:
            return False
        if drug and self.supported_drugs and drug not in self.supported_drugs:
            return False
        if population and self.supported_populations and population not in self.supported_populations:
            return False
        return True

    def summary(self) -> str:
        """Human-readable agent summary."""
        genes = ", ".join(self.supported_genes[:5]) or "all"
        pops = ", ".join(self.supported_populations[:5]) or "all"
        caps = ", ".join(self.capabilities[:3]) or "none"
        return (
            f"{self.name} [{self.domain.value}]\n"
            f"  {self.description}\n"
            f"  Genes: {genes} | Populations: {pops}\n"
            f"  Capabilities: {caps}\n"
            f"  Mode: {self.reasoning_mode.value} | Confidence: {self.confidence_profile.default_confidence}"
        )
