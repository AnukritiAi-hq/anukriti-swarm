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
      rejected at the mutation boundary
    • a biomedical ontology — it does not import MeSH, SNOMED,
      or UMLS; ancestry-aware pharmacogenomic reasoning only
    • a GraphRAG engine — retrieval over the graph is
      population-aware path traversal (commit 11), not embedding
      search
    • a hypothesis generator — edges only represent provenanced
      relations from CPIC / PharmGKB / peer-reviewed sources;
      every edge carries a required ProvenanceStamp

Population is a *first-class* node kind, not metadata. Edges like
``higher_frequency_in`` and ``supported_by`` carry the ancestry
context that drives retrieval priorities and evidence weighting.

Public surface (populated through phase 3):

    schema (commit 9):
      NodeKind / EdgeKind closed enums
      ProvenanceStamp / Node / Edge frozen records
    seed (commit 9):
      SEED_NODES / SEED_EDGES derived from in-tree CPIC + rules
      data
    graph (commit 10):
      PharmacogenomicKnowledgeGraph (in-memory adjacency-list KG;
        scope-enforcing mutators; deterministic reads)
    builder (commit 10):
      GraphContextBuilder (build_empty / build_default factories)
      PopulationGraphIndexer (population-keyed lookups:
        alleles_by_population / drugs_by_population /
        evidence_by_population; precomputed in O(graph) time)
    reasoner (commit 11):
      MultiHopReasoner + PathEvidenceRetriever

All modules are deterministic; no LLM calls in this package.
"""

from __future__ import annotations

from knowledge_graph.builder import (
    GraphContextBuilder,
    PopulationGraphIndexer,
)
from knowledge_graph.graph import PharmacogenomicKnowledgeGraph
from knowledge_graph.schema import (
    Edge,
    EdgeKind,
    Node,
    NodeKind,
    ProvenanceStamp,
)
from knowledge_graph.seed import SEED_EDGES, SEED_NODES

__all__ = [
    # schema
    "Edge",
    "EdgeKind",
    "Node",
    "NodeKind",
    "ProvenanceStamp",
    # seed
    "SEED_EDGES",
    "SEED_NODES",
    # graph
    "PharmacogenomicKnowledgeGraph",
    # builder + indexer
    "GraphContextBuilder",
    "PopulationGraphIndexer",
]
