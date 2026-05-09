"""Multi-strategy biomedical retrieval (phase 2 of the brief).

A policy-layer subpackage sitting on top of the existing
``retrieval/evidence`` and ``retrieval/indexing`` stacks. Does
**not** introduce a new vector store or document source; it
combines the existing retriever with ancestry-, graph-, and
diversity-aware selection so a caller can say "retrieve for
CYP2C19 + clopidogrel + SAS" and get a pharmacogenomically
relevant evidence set rather than a generic semantic top-k.

Public surface (populated through phase 2):

    BiomedicalQuery               frozen pharmacogenomic query
                                  (commit 6)
    RetrievalStrategyResult       frozen result wrapper carrying
                                  strategy + priorities (commit 6)
    BiomedicalRetriever           strategy ABC (commit 6)
    DenseSemanticRetriever        wraps existing EvidenceRetriever
                                  (commit 6)
    PopulationAwareRetriever      re-ranks by population alignment
                                  (commit 6)
    GraphRetriever                KG strategy — public surface final,
                                  internals are a documented phase-3
                                  stub (commit 7)
    EvidenceSelector              deterministic diversity + dedup
                                  merger across strategy outputs
                                  (commit 7)
    AdaptiveRetrievalController   sufficiency-aware loop (commit 8)

Scope-wise this subpackage is still pharmacogenomic-only. The
retrievers refuse queries that are not keyed on (gene, drug,
population, genotype) tuples.
"""

from __future__ import annotations

from retrieval.multi_strategy.biomedical_retriever import (
    BiomedicalQuery,
    BiomedicalRetriever,
    DenseSemanticRetriever,
    PopulationAwareRetriever,
    RetrievalStrategyResult,
)
from retrieval.multi_strategy.graph_and_selector import (
    EvidenceSelector,
    GraphRetriever,
)

__all__ = [
    "BiomedicalQuery",
    "BiomedicalRetriever",
    "DenseSemanticRetriever",
    "EvidenceSelector",
    "GraphRetriever",
    "PopulationAwareRetriever",
    "RetrievalStrategyResult",
]
