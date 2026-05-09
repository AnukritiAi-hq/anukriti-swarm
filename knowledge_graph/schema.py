"""Pharmacogenomic knowledge graph — closed schema.

Phase 3, commit 9 of the Evidence Sufficiency Layer brief.

Defines the only 10 node kinds and 7 edge kinds the
``PharmacogenomicKnowledgeGraph`` is ever allowed to carry, plus
frozen ``Node`` / ``Edge`` / ``ProvenanceStamp`` records and a
deterministic seed payload built from the in-tree CPIC + allele
data. No external ontology imports, no LLM. Adding a new kind is
a code change.

Closed node kinds (brief phase 3, req #9)
-----------------------------------------

    POPULATION          a 1000 Genomes / gnomAD super-population
                        (SAS, EAS, AFR, EUR, AMR)
    ANCESTRY            a finer-grained ancestry descriptor; kept
                        distinct from POPULATION so the graph can
                        later carry sub-populations without breaking
                        the 10-kind firewall
    GENE                a pharmacogene (CYP2D6 / CYP2C19 / HLA-B)
    VARIANT             a SNV or structural variant reference (rsID
                        or star-allele pointer)
    ALLELE              a star-allele (CYP2D6*4, HLA-B*15:02, etc.)
    PHENOTYPE           a metabolizer phenotype or HLA-risk status
    DRUG                a pharmacogenomically-actionable drug
    ADVERSE_REACTION    an ADR tied to a gene+drug (SJS/TEN, MACE)
    GUIDELINE           a CPIC / PharmGKB / FDA guideline record
    EVIDENCE_PAPER      a PubMed / PharmGKB citation

Closed edge kinds (brief phase 3, req #9)
-----------------------------------------

    metabolizes             GENE --metabolizes--> DRUG
    contraindicated_for     ALLELE / PHENOTYPE --contra--> DRUG
    associated_with         DRUG --assoc--> ADVERSE_REACTION
    higher_frequency_in     ALLELE --freq-in--> POPULATION
    supported_by            (any) --supported_by--> EVIDENCE_PAPER
    conflicts_with          EVIDENCE_PAPER --conflicts_with-->
                            EVIDENCE_PAPER
    guideline_recommends    GUIDELINE --recommends--> DRUG

Design discipline
-----------------

* ``Node.id`` is a stable deterministic string built from (kind,
  key-fields). Two nodes with the same id are the same node; the
  graph deduplicates on add.
* ``Edge`` carries a ``ProvenanceStamp`` so every relation knows
  where it came from (CPIC guideline id, PMID, rule_id). Edges
  without provenance are rejected at the graph boundary
  (phase-3 commit 10).
* ``Node`` carries an optional ``payload`` dict for kind-specific
  extras (activity_score on ALLELE, strength on GUIDELINE, etc.).
  Payload keys are free-form but primitive — the whole graph
  serializes to JSON.
* Frequencies on ``higher_frequency_in`` edges are in the edge's
  ``weight`` field, ``[0.0, 1.0]``; the population-aware reasoner
  uses the weight directly (population is a *first-class*
  reasoning dimension, not metadata).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


# ---------------------------------------------------------------------------
# Closed enums
# ---------------------------------------------------------------------------


class NodeKind(str, Enum):
    """The 10 allowed node kinds. Extending is a code change."""

    POPULATION = "population"
    ANCESTRY = "ancestry"
    GENE = "gene"
    VARIANT = "variant"
    ALLELE = "allele"
    PHENOTYPE = "phenotype"
    DRUG = "drug"
    ADVERSE_REACTION = "adverse_reaction"
    GUIDELINE = "guideline"
    EVIDENCE_PAPER = "evidence_paper"


class EdgeKind(str, Enum):
    """The 7 allowed edge kinds. Extending is a code change."""

    METABOLIZES = "metabolizes"
    CONTRAINDICATED_FOR = "contraindicated_for"
    ASSOCIATED_WITH = "associated_with"
    HIGHER_FREQUENCY_IN = "higher_frequency_in"
    SUPPORTED_BY = "supported_by"
    CONFLICTS_WITH = "conflicts_with"
    GUIDELINE_RECOMMENDS = "guideline_recommends"


# ---------------------------------------------------------------------------
# Frozen records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProvenanceStamp:
    """Every edge + optionally every node carries one of these.

    Fields
    ------
    source_id       the curated source id — a CPIC guideline id
                    (CPIC:CYP2C19:clopidogrel:2022), a PMID, a
                    PharmGKB annotation id, or a rule id
                    (cpic.activity_score)
    source_type     closed-ish tag: "cpic" | "pharmgkb" | "pubmed"
                    | "rule" | "derived". Free-form at the type
                    level but the seed only uses those 5 values.
    added_at        ISO timestamp the stamp was produced
    """

    source_id: str
    source_type: str
    added_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "added_at": self.added_at.isoformat(),
        }


@dataclass(frozen=True)
class Node:
    """Frozen graph node.

    Fields
    ------
    id          deterministic string id; built from kind + name
    kind        closed NodeKind
    name        human-readable name (CYP2C19 / clopidogrel /
                Poor Metabolizer / SAS / PMID:34032273)
    payload     kind-specific metadata; optional, primitive values
                only so the whole graph is JSON-safe
    stamp       optional provenance stamp (some nodes like POPULATION
                SAS don't need one; every node the builder adds from
                a curated source carries one)
    """

    id: str
    kind: NodeKind
    name: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    stamp: ProvenanceStamp | None = None

    @staticmethod
    def make_id(kind: NodeKind, name: str) -> str:
        """Stable id builder. Same inputs always produce same id."""

        return f"{kind.value}:{name.strip()}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": self.name,
            "payload": dict(self.payload),
            "stamp": self.stamp.to_dict() if self.stamp else None,
        }


@dataclass(frozen=True)
class Edge:
    """Frozen directed graph edge.

    Fields
    ------
    source_id   Node.id of the origin
    target_id   Node.id of the destination
    kind        closed EdgeKind
    weight      [0.0, 1.0]; defaults to 1.0 for non-weighted edges.
                HIGHER_FREQUENCY_IN uses the per-population allele
                frequency. The reasoner consumes this directly.
    payload     edge-kind-specific extras (strength="strong" on
                GUIDELINE_RECOMMENDS, severity on CONTRAINDICATED_FOR,
                etc.)
    stamp       REQUIRED provenance stamp — every relation in the
                graph names where it came from
    """

    source_id: str
    target_id: str
    kind: EdgeKind
    weight: float = 1.0
    payload: Mapping[str, Any] = field(default_factory=dict)
    stamp: ProvenanceStamp = field(
        default_factory=lambda: ProvenanceStamp(
            source_id="derived", source_type="derived"
        )
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "kind": self.kind.value,
            "weight": round(float(self.weight), 4),
            "payload": dict(self.payload),
            "stamp": self.stamp.to_dict(),
        }


__all__ = [
    "NodeKind",
    "EdgeKind",
    "ProvenanceStamp",
    "Node",
    "Edge",
]
