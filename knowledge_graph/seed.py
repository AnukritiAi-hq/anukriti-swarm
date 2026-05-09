"""Seed data for the pharmacogenomic knowledge graph.

Phase 3, commit 9. Pure data — no behaviour, no LLM. Every node
and edge here is derived from the in-tree CPIC guidelines
(``guidelines/cpic.py``), phenotype rules (``rules/phenotype_rules.py``),
and biomedical documents (``retrieval/evidence/documents.py``). We do
NOT import an external ontology and do NOT invent edges not
supported by those sources. Every edge carries a ``ProvenanceStamp``.

Node ids follow the ``NodeKind:name`` convention from
``knowledge_graph.schema.Node.make_id``. Ordering is deterministic
(see ``SEED_NODES`` and ``SEED_EDGES`` below): sorting the lists
through ``sorted(key=lambda n: n.id)`` yields the canonical order
consumers can rely on.

Coverage
--------
The seed covers the three flagship scenarios:

    CYP2C19 + clopidogrel + SAS population
    CYP2D6  + codeine     + AFR / EUR populations
    HLA-B   + carbamazepine + EAS population

Extending coverage for a new gene/drug pair is a code change here.
"""

from __future__ import annotations

from knowledge_graph.schema import (
    Edge,
    EdgeKind,
    Node,
    NodeKind,
    ProvenanceStamp,
)


def _stamp(source_id: str, source_type: str) -> ProvenanceStamp:
    """Convenience builder; keeps seed table readable."""

    return ProvenanceStamp(source_id=source_id, source_type=source_type)


def _node(kind: NodeKind, name: str, payload: dict | None = None,
          stamp: ProvenanceStamp | None = None) -> Node:
    return Node(
        id=Node.make_id(kind, name),
        kind=kind,
        name=name,
        payload=payload or {},
        stamp=stamp,
    )


def _edge(src: Node, tgt: Node, kind: EdgeKind,
          weight: float = 1.0, payload: dict | None = None,
          *, stamp: ProvenanceStamp) -> Edge:
    return Edge(
        source_id=src.id,
        target_id=tgt.id,
        kind=kind,
        weight=weight,
        payload=payload or {},
        stamp=stamp,
    )


# ---------------------------------------------------------------------------
# Populations (no provenance stamp — these are 1000 Genomes codes)
# ---------------------------------------------------------------------------


_POP_SAS = _node(NodeKind.POPULATION, "SAS",
                 {"label": "South Asian", "source_panel": "1000_genomes"})
_POP_EAS = _node(NodeKind.POPULATION, "EAS",
                 {"label": "East Asian", "source_panel": "1000_genomes"})
_POP_AFR = _node(NodeKind.POPULATION, "AFR",
                 {"label": "African", "source_panel": "1000_genomes"})
_POP_EUR = _node(NodeKind.POPULATION, "EUR",
                 {"label": "European", "source_panel": "1000_genomes"})
_POP_AMR = _node(NodeKind.POPULATION, "AMR",
                 {"label": "Admixed American", "source_panel": "1000_genomes"})

_POPS = [_POP_SAS, _POP_EAS, _POP_AFR, _POP_EUR, _POP_AMR]


# ---------------------------------------------------------------------------
# Genes
# ---------------------------------------------------------------------------


_GENE_CYP2C19 = _node(NodeKind.GENE, "CYP2C19",
                      {"chromosome": "10q23.33"},
                      _stamp("cpic.activity_score", "rule"))
_GENE_CYP2D6 = _node(NodeKind.GENE, "CYP2D6",
                     {"chromosome": "22q13.2"},
                     _stamp("cpic.activity_score", "rule"))
_GENE_HLA_B = _node(NodeKind.GENE, "HLA-B",
                    {"chromosome": "6p21.33"},
                    _stamp("cpic.hla_b.risk_allele", "rule"))


# ---------------------------------------------------------------------------
# Alleles (activity scores from rules/phenotype_rules.py)
# ---------------------------------------------------------------------------


_ALL_CYP2C19_2 = _node(NodeKind.ALLELE, "CYP2C19*2",
                       {"gene": "CYP2C19", "activity_score": 0.0,
                        "function": "no_function"},
                       _stamp("PA166169660", "pharmgkb"))
_ALL_CYP2C19_3 = _node(NodeKind.ALLELE, "CYP2C19*3",
                       {"gene": "CYP2C19", "activity_score": 0.0,
                        "function": "no_function"},
                       _stamp("PA166169660", "pharmgkb"))
_ALL_CYP2C19_17 = _node(NodeKind.ALLELE, "CYP2C19*17",
                        {"gene": "CYP2C19", "activity_score": 1.5,
                         "function": "increased_function"},
                        _stamp("PA166169660", "pharmgkb"))

_ALL_CYP2D6_4 = _node(NodeKind.ALLELE, "CYP2D6*4",
                      {"gene": "CYP2D6", "activity_score": 0.0,
                       "function": "no_function"},
                      _stamp("PMID:32722396", "pubmed"))
_ALL_CYP2D6_10 = _node(NodeKind.ALLELE, "CYP2D6*10",
                       {"gene": "CYP2D6", "activity_score": 0.5,
                        "function": "decreased_function"},
                       _stamp("PMID:35891234", "pubmed"))
_ALL_CYP2D6_17 = _node(NodeKind.ALLELE, "CYP2D6*17",
                       {"gene": "CYP2D6", "activity_score": 0.5,
                        "function": "decreased_function"},
                       _stamp("PMID:35891234", "pubmed"))

_ALL_HLAB_1502 = _node(NodeKind.ALLELE, "HLA-B*15:02",
                       {"gene": "HLA-B", "risk": "sjs_ten"},
                       _stamp("PMID:24407187", "pubmed"))


# ---------------------------------------------------------------------------
# Phenotypes (from rules/phenotype_rules.py PHENOTYPE_RANGES)
# ---------------------------------------------------------------------------


_PHEN_CYP2C19_PM = _node(NodeKind.PHENOTYPE, "CYP2C19 Poor Metabolizer",
                         {"gene": "CYP2C19", "score_range": [0.0, 0.0]},
                         _stamp("cpic.activity_score", "rule"))
_PHEN_CYP2C19_IM = _node(NodeKind.PHENOTYPE, "CYP2C19 Intermediate Metabolizer",
                         {"gene": "CYP2C19", "score_range": [0.5, 1.0]},
                         _stamp("cpic.activity_score", "rule"))
_PHEN_CYP2D6_PM = _node(NodeKind.PHENOTYPE, "CYP2D6 Poor Metabolizer",
                        {"gene": "CYP2D6", "score_range": [0.0, 0.0]},
                        _stamp("cpic.activity_score", "rule"))
_PHEN_HLAB_POS = _node(NodeKind.PHENOTYPE, "HLA-B*15:02 positive",
                       {"gene": "HLA-B", "carrier_status": "positive"},
                       _stamp("cpic.hla_b.risk_allele", "rule"))


# ---------------------------------------------------------------------------
# Drugs
# ---------------------------------------------------------------------------


_DRUG_CLOPIDOGREL = _node(NodeKind.DRUG, "clopidogrel",
                          {"class": "antiplatelet", "prodrug": True},
                          _stamp("CPIC:CYP2C19:clopidogrel:2022", "cpic"))
_DRUG_PRASUGREL = _node(NodeKind.DRUG, "prasugrel",
                        {"class": "antiplatelet"},
                        _stamp("CPIC:CYP2C19:clopidogrel:2022", "cpic"))
_DRUG_TICAGRELOR = _node(NodeKind.DRUG, "ticagrelor",
                         {"class": "antiplatelet"},
                         _stamp("CPIC:CYP2C19:clopidogrel:2022", "cpic"))
_DRUG_CODEINE = _node(NodeKind.DRUG, "codeine",
                      {"class": "opioid_analgesic", "prodrug": True},
                      _stamp("CPIC:CYP2D6:codeine:2023", "cpic"))
_DRUG_MORPHINE = _node(NodeKind.DRUG, "morphine",
                       {"class": "opioid_analgesic"},
                       _stamp("CPIC:CYP2D6:codeine:2023", "cpic"))
_DRUG_CBZ = _node(NodeKind.DRUG, "carbamazepine",
                  {"class": "anticonvulsant"},
                  _stamp("CPIC:HLA-B:carbamazepine:2014", "cpic"))


# ---------------------------------------------------------------------------
# Adverse reactions
# ---------------------------------------------------------------------------


_ADR_MACE = _node(NodeKind.ADVERSE_REACTION, "MACE",
                  {"full_name": "major adverse cardiovascular events"},
                  _stamp("CPIC:CYP2C19:clopidogrel:2022", "cpic"))
_ADR_SJS_TEN = _node(NodeKind.ADVERSE_REACTION, "SJS/TEN",
                     {"full_name": "Stevens-Johnson syndrome / "
                                   "toxic epidermal necrolysis"},
                     _stamp("CPIC:HLA-B:carbamazepine:2014", "cpic"))
_ADR_RESP_DEP = _node(NodeKind.ADVERSE_REACTION, "respiratory depression",
                      {"severity": "high"},
                      _stamp("CPIC:CYP2D6:codeine:2023", "cpic"))


# ---------------------------------------------------------------------------
# Guidelines
# ---------------------------------------------------------------------------


_GL_CYP2C19_CLOP = _node(NodeKind.GUIDELINE, "CPIC:CYP2C19:clopidogrel:2022",
                         {"version": "2022.1", "strength": "strong"},
                         _stamp("CPIC:CYP2C19:clopidogrel:2022", "cpic"))
_GL_CYP2D6_COD = _node(NodeKind.GUIDELINE, "CPIC:CYP2D6:codeine:2023",
                       {"version": "2023.1", "strength": "strong"},
                       _stamp("CPIC:CYP2D6:codeine:2023", "cpic"))
_GL_HLAB_CBZ = _node(NodeKind.GUIDELINE, "CPIC:HLA-B:carbamazepine:2014",
                     {"version": "2014.1", "strength": "strong"},
                     _stamp("CPIC:HLA-B:carbamazepine:2014", "cpic"))


# ---------------------------------------------------------------------------
# Evidence papers (PMIDs + PharmGKB annotations)
# ---------------------------------------------------------------------------


_EV_PMID_34032273 = _node(NodeKind.EVIDENCE_PAPER, "PMID:34032273",
                          {"year": 2021, "title":
                           "CPIC Guideline for CYP2C19 and Clopidogrel"},
                          _stamp("PMID:34032273", "pubmed"))
_EV_PMID_32722396 = _node(NodeKind.EVIDENCE_PAPER, "PMID:32722396",
                          {"year": 2020, "title":
                           "CPIC Guideline for CYP2D6 and Codeine"},
                          _stamp("PMID:32722396", "pubmed"))
_EV_PMID_24407187 = _node(NodeKind.EVIDENCE_PAPER, "PMID:24407187",
                          {"year": 2014, "title":
                           "CPIC Guideline for HLA-B and Carbamazepine"},
                          _stamp("PMID:24407187", "pubmed"))
_EV_PA_166169660 = _node(NodeKind.EVIDENCE_PAPER, "PA166169660",
                         {"year": 2023, "title":
                          "PharmGKB CYP2C19 Population Frequency"},
                         _stamp("PA166169660", "pharmgkb"))
_EV_PMID_35891234 = _node(NodeKind.EVIDENCE_PAPER, "PMID:35891234",
                          {"year": 2023, "title":
                           "CYP2D6 Allele Distribution in South Asian"},
                          _stamp("PMID:35891234", "pubmed"))
_EV_PMID_36123456 = _node(NodeKind.EVIDENCE_PAPER, "PMID:36123456",
                          {"year": 2023, "title":
                           "HLA-B*15:02 Prevalence in Southeast Asia"},
                          _stamp("PMID:36123456", "pubmed"))


# ---------------------------------------------------------------------------
# Assemble node list
# ---------------------------------------------------------------------------


SEED_NODES: list[Node] = [
    # populations
    *_POPS,
    # genes
    _GENE_CYP2C19, _GENE_CYP2D6, _GENE_HLA_B,
    # alleles
    _ALL_CYP2C19_2, _ALL_CYP2C19_3, _ALL_CYP2C19_17,
    _ALL_CYP2D6_4, _ALL_CYP2D6_10, _ALL_CYP2D6_17,
    _ALL_HLAB_1502,
    # phenotypes
    _PHEN_CYP2C19_PM, _PHEN_CYP2C19_IM, _PHEN_CYP2D6_PM, _PHEN_HLAB_POS,
    # drugs
    _DRUG_CLOPIDOGREL, _DRUG_PRASUGREL, _DRUG_TICAGRELOR,
    _DRUG_CODEINE, _DRUG_MORPHINE, _DRUG_CBZ,
    # adverse reactions
    _ADR_MACE, _ADR_SJS_TEN, _ADR_RESP_DEP,
    # guidelines
    _GL_CYP2C19_CLOP, _GL_CYP2D6_COD, _GL_HLAB_CBZ,
    # evidence
    _EV_PMID_34032273, _EV_PMID_32722396, _EV_PMID_24407187,
    _EV_PA_166169660, _EV_PMID_35891234, _EV_PMID_36123456,
]


# ---------------------------------------------------------------------------
# Edges — 7 closed kinds, every edge stamped
# ---------------------------------------------------------------------------


# METABOLIZES: gene -> drug
_edges_metabolizes = [
    _edge(_GENE_CYP2C19, _DRUG_CLOPIDOGREL, EdgeKind.METABOLIZES,
          payload={"direction": "bioactivation"},
          stamp=_stamp("CPIC:CYP2C19:clopidogrel:2022", "cpic")),
    _edge(_GENE_CYP2D6, _DRUG_CODEINE, EdgeKind.METABOLIZES,
          payload={"direction": "activation_to_morphine"},
          stamp=_stamp("CPIC:CYP2D6:codeine:2023", "cpic")),
]


# CONTRAINDICATED_FOR: phenotype/allele -> drug
_edges_contra = [
    # CYP2C19 PM/IM -> clopidogrel
    _edge(_PHEN_CYP2C19_PM, _DRUG_CLOPIDOGREL, EdgeKind.CONTRAINDICATED_FOR,
          payload={"strength": "strong", "action": "use_alternative"},
          stamp=_stamp("CPIC:CYP2C19:clopidogrel:2022", "cpic")),
    _edge(_PHEN_CYP2C19_IM, _DRUG_CLOPIDOGREL, EdgeKind.CONTRAINDICATED_FOR,
          payload={"strength": "moderate", "action": "use_alternative"},
          stamp=_stamp("CPIC:CYP2C19:clopidogrel:2022", "cpic")),
    # CYP2D6 PM -> codeine
    _edge(_PHEN_CYP2D6_PM, _DRUG_CODEINE, EdgeKind.CONTRAINDICATED_FOR,
          payload={"strength": "strong", "action": "avoid"},
          stamp=_stamp("CPIC:CYP2D6:codeine:2023", "cpic")),
    # HLA-B*15:02 positive -> carbamazepine
    _edge(_ALL_HLAB_1502, _DRUG_CBZ, EdgeKind.CONTRAINDICATED_FOR,
          payload={"strength": "strong", "action": "do_not_use"},
          stamp=_stamp("CPIC:HLA-B:carbamazepine:2014", "cpic")),
    _edge(_PHEN_HLAB_POS, _DRUG_CBZ, EdgeKind.CONTRAINDICATED_FOR,
          payload={"strength": "strong", "action": "do_not_use"},
          stamp=_stamp("CPIC:HLA-B:carbamazepine:2014", "cpic")),
]


# ASSOCIATED_WITH: drug -> adverse reaction + allele -> phenotype
_edges_assoc = [
    # drug -> adverse reaction
    _edge(_DRUG_CLOPIDOGREL, _ADR_MACE, EdgeKind.ASSOCIATED_WITH,
          payload={"mechanism": "reduced_platelet_inhibition"},
          stamp=_stamp("CPIC:CYP2C19:clopidogrel:2022", "cpic")),
    _edge(_DRUG_CBZ, _ADR_SJS_TEN, EdgeKind.ASSOCIATED_WITH,
          payload={"mechanism": "HLA-B*15:02_mediated"},
          stamp=_stamp("CPIC:HLA-B:carbamazepine:2014", "cpic")),
    _edge(_DRUG_CODEINE, _ADR_RESP_DEP, EdgeKind.ASSOCIATED_WITH,
          payload={"mechanism": "ultrarapid_morphine_formation"},
          stamp=_stamp("CPIC:CYP2D6:codeine:2023", "cpic")),
    # allele -> phenotype (CPIC activity-score rule)
    _edge(_ALL_CYP2C19_2, _PHEN_CYP2C19_PM, EdgeKind.ASSOCIATED_WITH,
          payload={"activity_score_contribution": 0.0,
                   "via": "diplotype_PM_when_homozygous"},
          stamp=_stamp("cpic.activity_score", "rule")),
    _edge(_ALL_CYP2C19_3, _PHEN_CYP2C19_PM, EdgeKind.ASSOCIATED_WITH,
          payload={"activity_score_contribution": 0.0,
                   "via": "diplotype_PM_when_homozygous"},
          stamp=_stamp("cpic.activity_score", "rule")),
    _edge(_ALL_CYP2C19_2, _PHEN_CYP2C19_IM, EdgeKind.ASSOCIATED_WITH,
          payload={"activity_score_contribution": 0.0,
                   "via": "diplotype_IM_when_heterozygous"},
          stamp=_stamp("cpic.activity_score", "rule")),
    _edge(_ALL_CYP2D6_4, _PHEN_CYP2D6_PM, EdgeKind.ASSOCIATED_WITH,
          payload={"activity_score_contribution": 0.0,
                   "via": "diplotype_PM_when_homozygous"},
          stamp=_stamp("cpic.activity_score", "rule")),
    _edge(_ALL_HLAB_1502, _PHEN_HLAB_POS, EdgeKind.ASSOCIATED_WITH,
          payload={"carrier_status": "positive"},
          stamp=_stamp("cpic.hla_b.risk_allele", "rule")),
]


# HIGHER_FREQUENCY_IN: allele -> population (weight = freq)
_edges_freq = [
    # CYP2C19*2 — flagship SAS 36%
    _edge(_ALL_CYP2C19_2, _POP_SAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.36, payload={"note": "loss of function; major clopidogrel"},
          stamp=_stamp("PA166169660", "pharmgkb")),
    _edge(_ALL_CYP2C19_2, _POP_EAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.30, stamp=_stamp("PA166169660", "pharmgkb")),
    _edge(_ALL_CYP2C19_2, _POP_AFR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.18, stamp=_stamp("PA166169660", "pharmgkb")),
    _edge(_ALL_CYP2C19_2, _POP_EUR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.15, stamp=_stamp("PA166169660", "pharmgkb")),
    # CYP2D6*4 — EUR 20%
    _edge(_ALL_CYP2D6_4, _POP_EUR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.20, stamp=_stamp("PMID:32722396", "pubmed")),
    _edge(_ALL_CYP2D6_4, _POP_AFR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.06, stamp=_stamp("PMID:32722396", "pubmed")),
    # CYP2D6*17 — AFR 20%
    _edge(_ALL_CYP2D6_17, _POP_AFR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.20, stamp=_stamp("PMID:35891234", "pubmed")),
    # CYP2D6*10 — SAS 7.5% / EAS higher
    _edge(_ALL_CYP2D6_10, _POP_SAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.075, stamp=_stamp("PMID:35891234", "pubmed")),
    _edge(_ALL_CYP2D6_10, _POP_EAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.40, stamp=_stamp("PMID:35891234", "pubmed")),
    # HLA-B*15:02 — EAS 8% (flagship SJS/TEN case)
    _edge(_ALL_HLAB_1502, _POP_EAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.08, payload={"note": "Southeast Asian prevalence"},
          stamp=_stamp("PMID:36123456", "pubmed")),
]


# SUPPORTED_BY: any node -> evidence paper
_edges_supported = [
    _edge(_PHEN_CYP2C19_PM, _EV_PMID_34032273, EdgeKind.SUPPORTED_BY,
          stamp=_stamp("PMID:34032273", "pubmed")),
    _edge(_PHEN_CYP2D6_PM, _EV_PMID_32722396, EdgeKind.SUPPORTED_BY,
          stamp=_stamp("PMID:32722396", "pubmed")),
    _edge(_PHEN_HLAB_POS, _EV_PMID_24407187, EdgeKind.SUPPORTED_BY,
          stamp=_stamp("PMID:24407187", "pubmed")),
    _edge(_ALL_CYP2C19_2, _EV_PA_166169660, EdgeKind.SUPPORTED_BY,
          stamp=_stamp("PA166169660", "pharmgkb")),
    _edge(_ALL_CYP2D6_17, _EV_PMID_35891234, EdgeKind.SUPPORTED_BY,
          stamp=_stamp("PMID:35891234", "pubmed")),
    _edge(_ALL_HLAB_1502, _EV_PMID_36123456, EdgeKind.SUPPORTED_BY,
          stamp=_stamp("PMID:36123456", "pubmed")),
]


# GUIDELINE_RECOMMENDS: guideline -> drug (for alternatives)
_edges_guideline_rec = [
    _edge(_GL_CYP2C19_CLOP, _DRUG_PRASUGREL, EdgeKind.GUIDELINE_RECOMMENDS,
          payload={"audience": "PM/IM", "reason": "alternative_antiplatelet"},
          stamp=_stamp("CPIC:CYP2C19:clopidogrel:2022", "cpic")),
    _edge(_GL_CYP2C19_CLOP, _DRUG_TICAGRELOR, EdgeKind.GUIDELINE_RECOMMENDS,
          payload={"audience": "PM/IM", "reason": "alternative_antiplatelet"},
          stamp=_stamp("CPIC:CYP2C19:clopidogrel:2022", "cpic")),
    _edge(_GL_CYP2D6_COD, _DRUG_MORPHINE, EdgeKind.GUIDELINE_RECOMMENDS,
          payload={"audience": "PM", "reason": "avoid_prodrug_activation"},
          stamp=_stamp("CPIC:CYP2D6:codeine:2023", "cpic")),
]


SEED_EDGES: list[Edge] = (
    _edges_metabolizes
    + _edges_contra
    + _edges_assoc
    + _edges_freq
    + _edges_supported
    + _edges_guideline_rec
)


__all__ = ["SEED_NODES", "SEED_EDGES"]
