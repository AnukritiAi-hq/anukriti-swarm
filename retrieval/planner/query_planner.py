"""Sub-query generation and retrieval planning (MA-RAG inspired).

Decomposes a complex pharmacogenomic query into targeted sub-queries
that can be independently retrieved and then synthesized.

MA-RAG pattern:
1. Analyze query → identify information needs
2. Generate sub-queries → one per information need
3. Route sub-queries → appropriate document sources
4. Merge results → synthesize with citation tracking

Future: LLM-based query decomposition for complex multi-hop questions.
Currently uses deterministic rule-based decomposition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from retrieval.evidence.documents import DocumentSource


@dataclass(frozen=True)
class SubQuery:
    """A single targeted sub-query for retrieval."""

    query_id: str
    text: str
    target_source: DocumentSource | None  # None = search all
    gene_filter: str | None = None
    drug_filter: str | None = None
    intent: str = ""  # "guideline", "frequency", "mechanism", "evidence"


@dataclass(frozen=True)
class RetrievalPlan:
    """A plan consisting of multiple sub-queries to execute."""

    plan_id: str
    original_query: str
    sub_queries: list[SubQuery]
    strategy: str  # "single", "multi_hop", "comparative"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class QueryPlanner:
    """Deterministic query planner for pharmacogenomic retrieval.

    Decomposes queries based on detected entities (genes, drugs, populations)
    and generates targeted sub-queries for each information need.

    Future: Will use LLM for complex multi-hop query decomposition.
    """

    def plan(self, query: str, gene: str | None = None, drug: str | None = None, population: str | None = None) -> RetrievalPlan:
        """Generate a retrieval plan from a query."""
        sub_queries: list[SubQuery] = []
        query_lower = query.lower()

        # Sub-query 1: Guideline lookup (always if gene+drug present)
        if gene and drug:
            sub_queries.append(SubQuery(
                query_id=f"sq_guideline_{gene}_{drug}",
                text=f"{gene} {drug} CPIC guideline recommendation",
                target_source=DocumentSource.CPIC,
                gene_filter=gene, drug_filter=drug,
                intent="guideline",
            ))

        # Sub-query 2: Mechanism/pathway (if gene present)
        if gene:
            sub_queries.append(SubQuery(
                query_id=f"sq_mechanism_{gene}",
                text=f"{gene} metabolizer phenotype mechanism pathway",
                target_source=None,
                gene_filter=gene,
                intent="mechanism",
            ))

        # Sub-query 3: Population context (if population mentioned)
        if population or "population" in query_lower or "frequency" in query_lower:
            pop_text = f"{gene or ''} allele frequency {population or 'population'}"
            sub_queries.append(SubQuery(
                query_id=f"sq_population_{gene or 'general'}",
                text=pop_text.strip(),
                target_source=DocumentSource.PHARMGKB,
                gene_filter=gene,
                intent="frequency",
            ))

        # Sub-query 4: Supporting evidence (always)
        if gene:
            sub_queries.append(SubQuery(
                query_id=f"sq_evidence_{gene}",
                text=f"{gene} {drug or ''} clinical evidence study".strip(),
                target_source=DocumentSource.PUBMED,
                gene_filter=gene,
                intent="evidence",
            ))

        # Fallback: if no structured decomposition, use raw query
        if not sub_queries:
            sub_queries.append(SubQuery(
                query_id="sq_raw",
                text=query,
                target_source=None,
                intent="general",
            ))

        strategy = "multi_hop" if len(sub_queries) > 1 else "single"

        return RetrievalPlan(
            plan_id=f"plan_{hash(query) % 10000:04d}",
            original_query=query,
            sub_queries=sub_queries,
            strategy=strategy,
        )
