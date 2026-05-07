"""Evidence retriever with ranking and citation extraction.

Executes retrieval plans by searching the vector index for each sub-query,
then extracts citations and computes relevance scores.

Every retrieved passage carries:
- Citation ID (PMID, guideline ID)
- Source document reference
- Relevance score
- Retrieval provenance (which sub-query, which index)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from retrieval.evidence.documents import BiomedicalDocument, DocumentSource
from retrieval.indexing.embeddings import VectorIndex
from retrieval.planner.query_planner import RetrievalPlan, SubQuery


@dataclass(frozen=True)
class Citation:
    """An extracted citation linking a claim to its source."""

    citation_id: str        # PMID or guideline ID
    source: DocumentSource
    title: str
    year: int
    url: str | None = None


@dataclass(frozen=True)
class RetrievedEvidence:
    """A single piece of retrieved evidence with full provenance."""

    evidence_id: str
    content: str
    citation: Citation
    relevance_score: float
    gene: str | None = None
    drug: str | None = None
    sub_query_id: str = ""
    intent: str = ""
    retrieval_method: str = "vector_index"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RetrievalResult:
    """Aggregated result from executing a retrieval plan."""

    plan_id: str
    query: str
    evidence: list[RetrievedEvidence] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    total_retrieved: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceRetriever:
    """Executes retrieval plans and extracts cited evidence.

    For each sub-query in a plan:
    1. Search vector index with filters
    2. Extract citations from matched documents
    3. Score and rank results
    4. Deduplicate across sub-queries
    """

    def __init__(self, index: VectorIndex | None = None) -> None:
        self._index = index or VectorIndex()
        self._index.index()

    def execute_plan(self, plan: RetrievalPlan, top_k_per_query: int = 3) -> RetrievalResult:
        """Execute a full retrieval plan and return aggregated evidence."""
        all_evidence: list[RetrievedEvidence] = []
        seen_docs: set[str] = set()

        for sq in plan.sub_queries:
            results = self._execute_sub_query(sq, top_k_per_query)
            for ev in results:
                if ev.citation.citation_id not in seen_docs:
                    all_evidence.append(ev)
                    seen_docs.add(ev.citation.citation_id)

        # Sort by relevance
        all_evidence.sort(key=lambda e: e.relevance_score, reverse=True)

        # Extract unique citations
        citations = list({ev.citation.citation_id: ev.citation for ev in all_evidence}.values())

        return RetrievalResult(
            plan_id=plan.plan_id,
            query=plan.original_query,
            evidence=all_evidence,
            citations=citations,
            total_retrieved=len(all_evidence),
        )

    def _execute_sub_query(self, sq: SubQuery, top_k: int) -> list[RetrievedEvidence]:
        """Execute a single sub-query against the index."""
        results = self._index.search(
            query=sq.text,
            top_k=top_k,
            gene_filter=sq.gene_filter,
            drug_filter=sq.drug_filter,
        )

        evidence: list[RetrievedEvidence] = []
        for doc, score in results:
            citation = self._extract_citation(doc)
            evidence.append(RetrievedEvidence(
                evidence_id=f"ev_{doc.doc_id}_{sq.query_id}",
                content=doc.content,
                citation=citation,
                relevance_score=round(score, 4),
                gene=doc.genes[0] if doc.genes else None,
                drug=doc.drugs[0] if doc.drugs else None,
                sub_query_id=sq.query_id,
                intent=sq.intent,
            ))

        return evidence

    def _extract_citation(self, doc: BiomedicalDocument) -> Citation:
        """Extract citation metadata from a document."""
        return Citation(
            citation_id=doc.citation_id,
            source=doc.source,
            title=doc.title,
            year=doc.year,
            url=doc.url,
        )
