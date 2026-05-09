"""Pharmacogenomic Knowledge Graph.

Population-aware, closed-schema graph over the exact 10 node kinds
and 7 edge kinds the brief (phase 3) names. Populated from the
repository's existing ``guidelines/`` + ``rules/`` data — no
external ingestion, no generic document crawl.

Scope firewall
--------------
This is **not**:

    • a generic knowledge graph — the schema is closed to the 10
      brief-named node kinds and 7 edge kinds; unknown kinds are
      rejected at construction time
    • a biomedical ontology — it does not import MeSH, SNOMED,
      or UMLS; ancestry-aware pharmacogenomic reasoning only
    • a GraphRAG engine — retrieval over the graph is
      population-aware path traversal, not embedding search
    • a hypothesis generator — edges only represent provenanced
      relations from CPIC / PharmGKB / peer-reviewed sources

Population is a *first-class* node kind, not metadata. Edges like
``higher_frequency_in`` and ``supported_by`` carry the ancestry
context that drives retrieval priorities and evidence weighting.

Sub-modules
-----------
    schema.py     closed-enum NodeKind + EdgeKind + provenance stamp
    graph.py      PharmacogenomicKnowledgeGraph (in-memory)
    builder.py    GraphContextBuilder + PopulationGraphIndexer
    reasoner.py   MultiHopReasoner + PathEvidenceRetriever

All modules are deterministic; no LLM calls in this package.
"""

from __future__ import annotations

__all__: list[str] = []
