"""Reusable interfaces and contracts for agent extensibility.

Defines Protocol-based interfaces that agents and analysis modules
must implement. These enable:
- Adding new agent types without modifying existing code
- Swapping implementations (mock → real MCP)
- Future multi-omics, federated analysis, and knowledge graph integration

Design: Uses Python Protocols (structural subtyping) so implementations
don't need to explicitly inherit — they just need to match the interface.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from core.models.agents import AuditEntry, VerificationReport
from core.models.genomics import GenomicVariant, Phenotype
from core.models.pharmacogenomics import Recommendation, RetrievalResult
from core.models.population import AlleleFrequency, PopulationContext


@runtime_checkable
class VariantAnalyzer(Protocol):
    """Interface for chromosome-level variant analysis.

    Implementors: Chromosome agents, structural variant analyzers,
    future multi-omics analyzers (expression, methylation).
    """

    def analyze_variants(self, variants: list[GenomicVariant]) -> list[Phenotype]:
        """Analyze variants and return phenotype assignments."""
        ...


@runtime_checkable
class FrequencyLookup(Protocol):
    """Interface for population allele frequency lookups.

    Implementors: Population agents, gnomAD MCP, 1000 Genomes MCP,
    future federated frequency databases.
    """

    def lookup_frequency(self, allele: str, population: str) -> AlleleFrequency | None:
        """Lookup allele frequency in a specific population."""
        ...


@runtime_checkable
class EvidenceRetriever(Protocol):
    """Interface for evidence retrieval from knowledge bases.

    Implementors: Retrieval agent, Qdrant MCP, PubMed MCP,
    future knowledge graph traversal engines.
    """

    def retrieve(self, query: str, top_k: int = 5, **filters: Any) -> list[RetrievalResult]:
        """Retrieve relevant evidence passages."""
        ...


@runtime_checkable
class RecommendationEngine(Protocol):
    """Interface for generating pharmacogenomic recommendations.

    Implementors: Pharmacogene agents, CPIC lookup engine,
    future ML-based recommendation systems.
    """

    def recommend(self, gene: str, phenotype: Phenotype, drug: str) -> Recommendation | None:
        """Generate a dosing recommendation for a gene/phenotype/drug combination."""
        ...


@runtime_checkable
class Verifier(Protocol):
    """Interface for output verification.

    Implementors: Verification agent, fact-checking modules,
    future automated validation pipelines.
    """

    def verify(self, agent_id: str, output: dict[str, Any]) -> VerificationReport:
        """Verify an agent's output and return a verification report."""
        ...


@runtime_checkable
class AuditLogger(Protocol):
    """Interface for audit trail logging.

    Implementors: In-memory logger, MongoDB audit writer,
    future blockchain-based immutable audit.
    """

    def log(self, entry: AuditEntry) -> None:
        """Append an audit entry to the trail."""
        ...


@runtime_checkable
class KnowledgeGraphQuery(Protocol):
    """Interface for knowledge graph integration (future).

    Implementors: Neo4j connector, RDF/SPARQL engine,
    pharmacogenomic ontology traversal.
    """

    def query_relationships(self, entity: str, relationship: str) -> list[dict[str, Any]]:
        """Query relationships from a knowledge graph."""
        ...


@runtime_checkable
class FederatedAnalyzer(Protocol):
    """Interface for federated multi-site analysis (future).

    Implementors: Federated learning coordinator,
    cross-institutional frequency aggregator.
    """

    def submit_query(self, query: dict[str, Any]) -> str:
        """Submit a federated query and return a job ID."""
        ...

    def get_result(self, job_id: str) -> dict[str, Any] | None:
        """Retrieve federated query result."""
        ...
