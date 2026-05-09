"""Multi-strategy biomedical retrieval (phase 2 of the brief).

A policy-layer subpackage sitting on top of the existing
``retrieval/evidence`` and ``retrieval/indexing`` stacks. Does
**not** introduce a new vector store or document source; it
combines the existing retriever with ancestry-, graph-, and
diversity-aware selection so a caller can say "retrieve for
CYP2C19 + clopidogrel + SAS" and get a pharmacogenomically
relevant evidence set rather than a generic semantic top-k.

Populated in phase 2:

    BiomedicalRetriever            strategy interface; the existing
                                   ``EvidenceRetriever`` is its first
                                   concrete implementation
    PopulationAwareRetriever       re-ranks + biases retrieval by
                                   super-population (uses core.models
                                   ``SuperPopulation``)
    GraphRetriever                 thin adapter around
                                   ``knowledge_graph.MultiHopReasoner``
    EvidenceSelector               diversity + dedup over candidate set
    AdaptiveRetrievalController    loops retrieval until sufficiency
                                   or budget is reached (works with
                                   ``retrieval.stopping``)

Scope-wise this subpackage is still pharmacogenomic-only. The
retrievers refuse queries that are not keyed on (gene, drug,
population, genotype) tuples.
"""

from __future__ import annotations

__all__: list[str] = []
