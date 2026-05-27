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
# DPYD — fluoropyrimidine metabolism gene; CPIC level A for both
# 5-fluorouracil and capecitabine (PMID:29152729).
_GENE_DPYD = _node(NodeKind.GENE, "DPYD",
                   {"chromosome": "1p21.3"},
                   _stamp("cpic.activity_score", "rule"))


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


# DPYD alleles — activity scores from CPIC 2017 + Nov 2018 update
# (PMID:29152729). The four-variant European-canonical panel plus
# the c.1236G>A HapB3 tag SNP. Allele ids must match the form
# `allele:DPYD*<suffix>` so _pop_result_for() in core/runtime/runtime.py
# can match them by simple lstrip("*"); non-star labels (`c.2846A>T`,
# `HapB3`) are accepted as opaque strings by the indexer.
_ALL_DPYD_2A = _node(NodeKind.ALLELE, "DPYD*2A",
                     {"gene": "DPYD", "activity_score": 0.0,
                      "function": "no_function",
                      "rsid": "rs3918290",
                      "hgvs": "c.1905+1G>A"},
                     _stamp("PMID:29152729", "pubmed"))
_ALL_DPYD_13 = _node(NodeKind.ALLELE, "DPYD*13",
                     {"gene": "DPYD", "activity_score": 0.0,
                      "function": "no_function",
                      "rsid": "rs55886062",
                      "hgvs": "c.1679T>G p.Ile560Ser"},
                     _stamp("PMID:29152729", "pubmed"))
_ALL_DPYD_2846 = _node(NodeKind.ALLELE, "DPYD*c.2846A>T",
                       {"gene": "DPYD", "activity_score": 0.5,
                        "function": "decreased_function",
                        "rsid": "rs67376798",
                        "hgvs": "c.2846A>T p.Asp949Val"},
                       _stamp("PMID:29152729", "pubmed"))
_ALL_DPYD_HAPB3 = _node(NodeKind.ALLELE, "DPYD*HapB3",
                        {"gene": "DPYD", "activity_score": 0.5,
                         "function": "decreased_function",
                         "rsid_proxy": "rs56038477",
                         "rsid_causal": "rs75017182",
                         "hgvs": "c.1129-5923C>G (tagged by c.1236G>A)"},
                        _stamp("PMID:29152729", "pubmed"))


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


# DPYD phenotypes — CPIC 2017 + Nov 2018 update activity-score buckets.
# Note: AS=1.0 and AS=1.5 both map to Intermediate Metabolizer per the
# Nov 2018 update (collapsed to a single 50% dose-reduction bucket).
_PHEN_DPYD_NM = _node(NodeKind.PHENOTYPE, "DPYD Normal Metabolizer",
                      {"gene": "DPYD", "score_range": [2.0, 2.0]},
                      _stamp("cpic.activity_score", "rule"))
_PHEN_DPYD_IM = _node(NodeKind.PHENOTYPE, "DPYD Intermediate Metabolizer",
                      {"gene": "DPYD", "score_range": [1.0, 1.5]},
                      _stamp("cpic.activity_score", "rule"))
_PHEN_DPYD_PM = _node(NodeKind.PHENOTYPE, "DPYD Poor Metabolizer",
                      {"gene": "DPYD", "score_range": [0.0, 0.5]},
                      _stamp("cpic.activity_score", "rule"))


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


# Fluoropyrimidines — capecitabine is the oral prodrug of 5-fluorouracil.
_DRUG_5FU = _node(NodeKind.DRUG, "fluorouracil",
                  {"class": "fluoropyrimidine", "antimetabolite": True,
                   "aliases": ["5-FU", "5-fluorouracil"]},
                  _stamp("CPIC:DPYD:fluoropyrimidines:2017", "cpic"))
_DRUG_CAPECITABINE = _node(NodeKind.DRUG, "capecitabine",
                           {"class": "fluoropyrimidine",
                            "prodrug": True,
                            "active_metabolite": "fluorouracil"},
                           _stamp("CPIC:DPYD:fluoropyrimidines:2017", "cpic"))


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


_ADR_FP_TOX = _node(
    NodeKind.ADVERSE_REACTION,
    "fluoropyrimidine toxicity",
    {"severity": "grade_3_to_5",
     "manifestations": "myelosuppression, mucositis, hand-foot syndrome, neurotoxicity",
     "fatal_rate": "~1-2% in unscreened DPD-deficient carriers"},
    _stamp("PMID:29152729", "pubmed"),
)


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
_GL_DPYD_FP = _node(NodeKind.GUIDELINE, "CPIC:DPYD:fluoropyrimidines:2017",
                    {"version": "2018.1", "strength": "strong"},
                    _stamp("CPIC:DPYD:fluoropyrimidines:2017", "cpic"))


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
_EV_PMID_29152729 = _node(NodeKind.EVIDENCE_PAPER, "PMID:29152729",
                          {"year": 2018, "title":
                           "CPIC Guideline for DPYD and Fluoropyrimidines (2017 + Nov 2018)"},
                          _stamp("PMID:29152729", "pubmed"))
_EV_PMID_29239269 = _node(NodeKind.EVIDENCE_PAPER, "PMID:29239269",
                          {"year": 2018, "title":
                           "Pharmacogenetic Landscape of DPYD in South Asian Populations"},
                          _stamp("PMID:29239269", "pubmed"))
_EV_PMID_38886557 = _node(NodeKind.EVIDENCE_PAPER, "PMID:38886557",
                          {"year": 2024, "title":
                           "DPYD Polymorphisms in Non-European Patients with Severe FP Toxicity"},
                          _stamp("PMID:38886557", "pubmed"))


# ---------------------------------------------------------------------------
# Assemble node list
# ---------------------------------------------------------------------------


SEED_NODES: list[Node] = [
    # populations
    *_POPS,
    # genes
    _GENE_CYP2C19, _GENE_CYP2D6, _GENE_HLA_B, _GENE_DPYD,
    # alleles
    _ALL_CYP2C19_2, _ALL_CYP2C19_3, _ALL_CYP2C19_17,
    _ALL_CYP2D6_4, _ALL_CYP2D6_10, _ALL_CYP2D6_17,
    _ALL_HLAB_1502,
    _ALL_DPYD_2A, _ALL_DPYD_13, _ALL_DPYD_2846, _ALL_DPYD_HAPB3,
    # phenotypes
    _PHEN_CYP2C19_PM, _PHEN_CYP2C19_IM, _PHEN_CYP2D6_PM, _PHEN_HLAB_POS,
    _PHEN_DPYD_NM, _PHEN_DPYD_IM, _PHEN_DPYD_PM,
    # drugs
    _DRUG_CLOPIDOGREL, _DRUG_PRASUGREL, _DRUG_TICAGRELOR,
    _DRUG_CODEINE, _DRUG_MORPHINE, _DRUG_CBZ,
    _DRUG_5FU, _DRUG_CAPECITABINE,
    # adverse reactions
    _ADR_MACE, _ADR_SJS_TEN, _ADR_RESP_DEP, _ADR_FP_TOX,
    # guidelines
    _GL_CYP2C19_CLOP, _GL_CYP2D6_COD, _GL_HLAB_CBZ, _GL_DPYD_FP,
    # evidence
    _EV_PMID_34032273, _EV_PMID_32722396, _EV_PMID_24407187,
    _EV_PA_166169660, _EV_PMID_35891234, _EV_PMID_36123456,
    _EV_PMID_29152729, _EV_PMID_29239269, _EV_PMID_38886557,
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
    _edge(_ALL_CYP2C19_2, _POP_AMR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.10, stamp=_stamp("PA166169660", "pharmgkb")),
    # CYP2C19*3 — EAS 8% (rare elsewhere; rounded floor 0.01 to keep
    # the edge present so wildtype-baseline math reflects population coverage)
    _edge(_ALL_CYP2C19_3, _POP_EAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.08, stamp=_stamp("PA166169660", "pharmgkb")),
    _edge(_ALL_CYP2C19_3, _POP_SAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.02, stamp=_stamp("PA166169660", "pharmgkb")),
    _edge(_ALL_CYP2C19_3, _POP_AFR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.01, stamp=_stamp("PA166169660", "pharmgkb")),
    # CYP2C19*17 — increased function; well-studied in EUR (~21%)
    _edge(_ALL_CYP2C19_17, _POP_EUR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.21, stamp=_stamp("PA166169660", "pharmgkb")),
    _edge(_ALL_CYP2C19_17, _POP_AFR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.22, stamp=_stamp("PA166169660", "pharmgkb")),
    _edge(_ALL_CYP2C19_17, _POP_SAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.18, stamp=_stamp("PA166169660", "pharmgkb")),
    _edge(_ALL_CYP2C19_17, _POP_AMR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.17, stamp=_stamp("PA166169660", "pharmgkb")),
    # CYP2C19*17 — EAS rare (~2%)
    _edge(_ALL_CYP2C19_17, _POP_EAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.02, stamp=_stamp("PA166169660", "pharmgkb")),
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


# ---------------------------------------------------------------------------
# DPYD / fluoropyrimidine edges (CPIC 2017 + Nov 2018 update; PMID:29152729)
# ---------------------------------------------------------------------------

# METABOLIZES: DPYD inactivates 5-FU (and capecitabine via 5-FU)
_edges_dpyd_metabolizes = [
    _edge(_GENE_DPYD, _DRUG_5FU, EdgeKind.METABOLIZES,
          payload={"direction": "inactivation",
                   "fraction": "80-90% of administered 5-FU"},
          stamp=_stamp("CPIC:DPYD:fluoropyrimidines:2017", "cpic")),
    _edge(_GENE_DPYD, _DRUG_CAPECITABINE, EdgeKind.METABOLIZES,
          payload={"direction": "inactivation_via_5fu",
                   "note": "capecitabine -> 5-FU -> DPD-mediated catabolism"},
          stamp=_stamp("CPIC:DPYD:fluoropyrimidines:2017", "cpic")),
]

# CONTRAINDICATED_FOR: DPYD PM strongly avoids; IM dose-reduce 50%
_edges_dpyd_contra = [
    _edge(_PHEN_DPYD_PM, _DRUG_5FU, EdgeKind.CONTRAINDICATED_FOR,
          payload={"strength": "strong", "action": "avoid",
                   "fallback": "if no alternative: <25% of standard dose + therapeutic drug monitoring"},
          stamp=_stamp("CPIC:DPYD:fluoropyrimidines:2017", "cpic")),
    _edge(_PHEN_DPYD_PM, _DRUG_CAPECITABINE, EdgeKind.CONTRAINDICATED_FOR,
          payload={"strength": "strong", "action": "avoid"},
          stamp=_stamp("CPIC:DPYD:fluoropyrimidines:2017", "cpic")),
    _edge(_PHEN_DPYD_IM, _DRUG_5FU, EdgeKind.CONTRAINDICATED_FOR,
          payload={"strength": "moderate", "action": "dose_reduce_50_pct",
                   "note": "CPIC Nov 2018: AS=1.0 and AS=1.5 both 50%"},
          stamp=_stamp("CPIC:DPYD:fluoropyrimidines:2017", "cpic")),
    _edge(_PHEN_DPYD_IM, _DRUG_CAPECITABINE, EdgeKind.CONTRAINDICATED_FOR,
          payload={"strength": "moderate", "action": "dose_reduce_50_pct"},
          stamp=_stamp("CPIC:DPYD:fluoropyrimidines:2017", "cpic")),
]

# ASSOCIATED_WITH:
#   drug -> adverse reaction
#   allele -> phenotype (activity-score additive rule)
_edges_dpyd_assoc = [
    _edge(_DRUG_5FU, _ADR_FP_TOX, EdgeKind.ASSOCIATED_WITH,
          payload={"mechanism": "DPD_deficiency_5FU_accumulation"},
          stamp=_stamp("PMID:29152729", "pubmed")),
    _edge(_DRUG_CAPECITABINE, _ADR_FP_TOX, EdgeKind.ASSOCIATED_WITH,
          payload={"mechanism": "DPD_deficiency_5FU_accumulation"},
          stamp=_stamp("PMID:29152729", "pubmed")),
    # No-function alleles -> PM (homozygous combinations)
    _edge(_ALL_DPYD_2A, _PHEN_DPYD_PM, EdgeKind.ASSOCIATED_WITH,
          payload={"activity_score_contribution": 0.0,
                   "via": "homozygous_or_compound_no_function"},
          stamp=_stamp("cpic.activity_score", "rule")),
    _edge(_ALL_DPYD_13, _PHEN_DPYD_PM, EdgeKind.ASSOCIATED_WITH,
          payload={"activity_score_contribution": 0.0,
                   "via": "homozygous_or_compound_no_function"},
          stamp=_stamp("cpic.activity_score", "rule")),
    # Decreased-function alleles -> IM
    _edge(_ALL_DPYD_2846, _PHEN_DPYD_IM, EdgeKind.ASSOCIATED_WITH,
          payload={"activity_score_contribution": 0.5,
                   "via": "diplotype_IM_when_heterozygous"},
          stamp=_stamp("cpic.activity_score", "rule")),
    _edge(_ALL_DPYD_HAPB3, _PHEN_DPYD_IM, EdgeKind.ASSOCIATED_WITH,
          payload={"activity_score_contribution": 0.5,
                   "via": "diplotype_IM_when_heterozygous"},
          stamp=_stamp("cpic.activity_score", "rule")),
    # No-function het + wildtype -> IM (also covered by activity score)
    _edge(_ALL_DPYD_2A, _PHEN_DPYD_IM, EdgeKind.ASSOCIATED_WITH,
          payload={"activity_score_contribution": 0.0,
                   "via": "diplotype_IM_when_heterozygous_with_wildtype"},
          stamp=_stamp("cpic.activity_score", "rule")),
    _edge(_ALL_DPYD_13, _PHEN_DPYD_IM, EdgeKind.ASSOCIATED_WITH,
          payload={"activity_score_contribution": 0.0,
                   "via": "diplotype_IM_when_heterozygous_with_wildtype"},
          stamp=_stamp("cpic.activity_score", "rule")),
]

# HIGHER_FREQUENCY_IN: gnomAD v4.0 numbers from
# datasets/pharmfreq/allele_frequencies.py — these populate
# _pop_result_for() in core/runtime/runtime.py so the POPULATION facet
# can resolve for any cohort run that lands on a non-wildtype DPYD
# allele. Sample sizes per population per gnomAD v4.0:
#   SAS=15308, AFR=20744, EUR=64603, EAS=9197, AMR=7647.
_edges_dpyd_freq = [
    # *2A (no function) — EUR-enriched
    _edge(_ALL_DPYD_2A, _POP_EUR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.012, payload={"note": "splice donor c.1905+1G>A; canonical European panel"},
          stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_2A, _POP_AMR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.006, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_2A, _POP_SAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.005, payload={"note": "present in SAS but lower than EUR; Hariprakash 2018"},
          stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_2A, _POP_EAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.001, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_2A, _POP_AFR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.001, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    # *13 (no function) — globally rare
    _edge(_ALL_DPYD_13, _POP_EUR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.002, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_13, _POP_SAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.001, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_13, _POP_AFR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.001, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_13, _POP_EAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.001, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_13, _POP_AMR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.001, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    # c.2846A>T (decreased function) — EUR-enriched
    _edge(_ALL_DPYD_2846, _POP_EUR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.006, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_2846, _POP_AMR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.004, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_2846, _POP_SAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.003, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_2846, _POP_AFR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.001, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_2846, _POP_EAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.001, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    # HapB3 (decreased function) — EUR-enriched (~2.2%)
    _edge(_ALL_DPYD_HAPB3, _POP_EUR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.022, payload={"note": "tagged by c.1236G>A rs56038477"},
          stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_HAPB3, _POP_AMR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.010, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_HAPB3, _POP_SAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.005, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_HAPB3, _POP_AFR, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.002, stamp=_stamp("gnomAD:v4.0", "gnomad")),
    _edge(_ALL_DPYD_HAPB3, _POP_EAS, EdgeKind.HIGHER_FREQUENCY_IN,
          weight=0.001, stamp=_stamp("gnomAD:v4.0", "gnomad")),
]

# SUPPORTED_BY: hook the new evidence papers to DPYD nodes
_edges_dpyd_supported = [
    _edge(_PHEN_DPYD_PM, _EV_PMID_29152729, EdgeKind.SUPPORTED_BY,
          stamp=_stamp("PMID:29152729", "pubmed")),
    _edge(_PHEN_DPYD_IM, _EV_PMID_29152729, EdgeKind.SUPPORTED_BY,
          stamp=_stamp("PMID:29152729", "pubmed")),
    _edge(_PHEN_DPYD_NM, _EV_PMID_29152729, EdgeKind.SUPPORTED_BY,
          stamp=_stamp("PMID:29152729", "pubmed")),
    _edge(_ALL_DPYD_2A, _EV_PMID_29152729, EdgeKind.SUPPORTED_BY,
          stamp=_stamp("PMID:29152729", "pubmed")),
    _edge(_ALL_DPYD_13, _EV_PMID_29152729, EdgeKind.SUPPORTED_BY,
          stamp=_stamp("PMID:29152729", "pubmed")),
    _edge(_ALL_DPYD_2846, _EV_PMID_29152729, EdgeKind.SUPPORTED_BY,
          stamp=_stamp("PMID:29152729", "pubmed")),
    _edge(_ALL_DPYD_HAPB3, _EV_PMID_29152729, EdgeKind.SUPPORTED_BY,
          stamp=_stamp("PMID:29152729", "pubmed")),
    # Equity anchors
    _edge(_GENE_DPYD, _EV_PMID_29239269, EdgeKind.SUPPORTED_BY,
          payload={"context": "South Asian DPYD landscape"},
          stamp=_stamp("PMID:29239269", "pubmed")),
    _edge(_GENE_DPYD, _EV_PMID_38886557, EdgeKind.SUPPORTED_BY,
          payload={"context": "non-European systematic review"},
          stamp=_stamp("PMID:38886557", "pubmed")),
]

# GUIDELINE_RECOMMENDS: alternatives for DPYD PM (avoid 5-FU/cape; tegafur
# also DPD-metabolised so NOT a safe alternative — represented as
# explicit absence rather than a positive edge to avoid implying
# substitutability the CPIC guideline forbids).


SEED_EDGES: list[Edge] = (
    _edges_metabolizes
    + _edges_contra
    + _edges_assoc
    + _edges_freq
    + _edges_supported
    + _edges_guideline_rec
    + _edges_dpyd_metabolizes
    + _edges_dpyd_contra
    + _edges_dpyd_assoc
    + _edges_dpyd_freq
    + _edges_dpyd_supported
)


__all__ = ["SEED_NODES", "SEED_EDGES"]
