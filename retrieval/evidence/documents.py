"""Mock biomedical document store.

Simulates CPIC guidelines, PharmGKB annotations, and PubMed abstracts
for retrieval testing. Each document carries full provenance metadata.

Future: Will be replaced by MCP-based access to real databases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class DocumentSource(str, Enum):
    CPIC = "CPIC"
    PHARMGKB = "PharmGKB"
    PUBMED = "PubMed"
    FDA = "FDA"


@dataclass(frozen=True)
class BiomedicalDocument:
    """A single retrievable biomedical document with provenance."""

    doc_id: str
    source: DocumentSource
    title: str
    content: str
    genes: list[str]
    drugs: list[str]
    keywords: list[str]
    citation_id: str        # PMID, guideline ID, or annotation ID
    year: int
    url: str | None = None
    indexed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# --- CPIC Guideline Documents ---

CPIC_DOCUMENTS: list[BiomedicalDocument] = [
    BiomedicalDocument(
        doc_id="cpic_cyp2d6_codeine",
        source=DocumentSource.CPIC,
        title="CPIC Guideline for CYP2D6 and Codeine Therapy",
        content=(
            "Codeine is a prodrug that requires CYP2D6-mediated O-demethylation to morphine "
            "for analgesic effect. Poor metabolizers have significantly reduced morphine formation "
            "and may experience inadequate pain relief. Ultrarapid metabolizers form morphine at "
            "higher rates, increasing risk of toxicity including respiratory depression. "
            "Intermediate metabolizers have reduced but not absent morphine formation. "
            "Alternative analgesics should be considered for PM and UM patients."
        ),
        genes=["CYP2D6"], drugs=["codeine", "morphine"],
        keywords=["metabolizer", "prodrug", "analgesic", "respiratory depression"],
        citation_id="PMID:32722396", year=2020,
    ),
    BiomedicalDocument(
        doc_id="cpic_cyp2c19_clopidogrel",
        source=DocumentSource.CPIC,
        title="CPIC Guideline for CYP2C19 and Clopidogrel Therapy",
        content=(
            "Clopidogrel is a prodrug requiring CYP2C19-mediated bioactivation. Poor and "
            "intermediate metabolizers have reduced active metabolite formation, leading to "
            "diminished platelet inhibition and increased risk of major adverse cardiovascular "
            "events (MACE). Alternative antiplatelet agents (prasugrel, ticagrelor) that do not "
            "require CYP2C19 activation should be considered for PM and IM patients."
        ),
        genes=["CYP2C19"], drugs=["clopidogrel", "prasugrel", "ticagrelor"],
        keywords=["antiplatelet", "prodrug", "MACE", "platelet inhibition"],
        citation_id="PMID:34032273", year=2021,
    ),
    BiomedicalDocument(
        doc_id="cpic_hlab_carbamazepine",
        source=DocumentSource.CPIC,
        title="CPIC Guideline for HLA-B and Carbamazepine Therapy",
        content=(
            "HLA-B*15:02 allele carriers have a significantly elevated risk of carbamazepine-induced "
            "Stevens-Johnson syndrome (SJS) and toxic epidermal necrolysis (TEN). The allele is "
            "most prevalent in Southeast Asian populations. Genetic testing is recommended before "
            "initiating carbamazepine therapy. Carriers should not be prescribed carbamazepine "
            "or oxcarbazepine."
        ),
        genes=["HLA-B"], drugs=["carbamazepine", "oxcarbazepine"],
        keywords=["SJS", "TEN", "hypersensitivity", "HLA", "Southeast Asian"],
        citation_id="PMID:24407187", year=2014,
    ),
    BiomedicalDocument(
        # The canonical engine-side document for the DPYD/fluoropyrimidine
        # workflow. Without this, the swarm runtime fires V5 INSUFFICIENT
        # on every fluorouracil run because no document covers the
        # (DPYD, fluorouracil) facet pair.
        doc_id="cpic_dpyd_fluoropyrimidines",
        source=DocumentSource.CPIC,
        title="CPIC Guideline for DPYD and Fluoropyrimidines (2017 + Nov 2018 Update)",
        content=(
            "Dihydropyrimidine dehydrogenase (DPD) inactivates 80-90% of administered "
            "5-fluorouracil. Loss-of-function DPYD variants (c.1905+1G>A / *2A, c.1679T>G / *13) "
            "and decreased-function variants (c.2846A>T, c.1129-5923C>G or its tag c.1236G>A / "
            "HapB3) increase risk of severe (Grade 3+) fluoropyrimidine toxicity, including "
            "myelosuppression, mucositis, hand-foot syndrome, and neurotoxicity, with 1-2% "
            "treatment-related mortality in unscreened carriers. Recommendations are keyed on "
            "the DPYD activity score (sum of two lowest variant scores): score 2 = Normal "
            "Metabolizer (standard dose); score 1 or 1.5 = Intermediate Metabolizer (50% dose "
            "reduction per the November 2018 update, with possible >50% reduction for the "
            "homozygous c.[2846A>T];[2846A>T] genotype); score 0 or 0.5 = Poor Metabolizer "
            "(avoid 5-fluorouracil and prodrug-based regimens, including capecitabine and "
            "tegafur). Tegafur is also DPD-metabolized and is NOT a safe alternative. Uridine "
            "triacetate (Vistogard) is the FDA-approved rescue for 5-FU overdose. The CPIC "
            "guideline applies to fluorouracil and capecitabine; tegafur is covered by the "
            "DPWG guideline (Lunenburg 2020). FDA boxed warning on capecitabine and the NCCN "
            "colon-cancer guideline now recommend pre-treatment DPYD testing."
        ),
        genes=["DPYD"],
        drugs=["fluorouracil", "5-fluorouracil", "5-FU", "capecitabine", "tegafur"],
        keywords=[
            "DPD deficiency",
            "fluoropyrimidine toxicity",
            "activity score",
            "myelosuppression",
            "mucositis",
            "hand-foot syndrome",
            "uridine triacetate",
            "European",
            "intermediate metabolizer",
            "poor metabolizer",
        ],
        citation_id="PMID:29152729", year=2018,
    ),
]

# --- PharmGKB Annotations ---

PHARMGKB_DOCUMENTS: list[BiomedicalDocument] = [
    BiomedicalDocument(
        doc_id="pgkb_cyp2d6_tamoxifen",
        source=DocumentSource.PHARMGKB,
        title="PharmGKB: CYP2D6 and Tamoxifen Pathway",
        content=(
            "Tamoxifen is metabolized by CYP2D6 to its active metabolite endoxifen. "
            "CYP2D6 poor metabolizers have significantly lower endoxifen concentrations "
            "and may have reduced therapeutic benefit from tamoxifen in breast cancer treatment. "
            "CPIC recommends considering aromatase inhibitors as alternatives for PM patients."
        ),
        genes=["CYP2D6"], drugs=["tamoxifen", "endoxifen"],
        keywords=["breast cancer", "endocrine therapy", "endoxifen", "aromatase inhibitor"],
        citation_id="PA166104949", year=2022,
    ),
    BiomedicalDocument(
        doc_id="pgkb_cyp2c19_population",
        source=DocumentSource.PHARMGKB,
        title="PharmGKB: CYP2C19 Allele Frequency by Population",
        content=(
            "CYP2C19*2 is the most common loss-of-function allele globally. Frequency varies "
            "significantly by population: ~36% in South Asians, ~30% in East Asians, ~15% in "
            "Europeans, and ~18% in Africans. This means intermediate and poor metabolizer "
            "phenotypes are substantially more prevalent in Asian populations, with major "
            "implications for clopidogrel prescribing in these regions."
        ),
        genes=["CYP2C19"], drugs=["clopidogrel"],
        # Includes EUR + the well-served Asian / Latino populations.
        # AFR is deliberately omitted — the platform's evidence-sufficiency
        # layer needs to keep flagging AFR-specific gaps until real
        # AFR-focused publications are added to the seed (tracked in
        # `evidence_sufficiency_demo` as the canonical refusal case).
        keywords=[
            "allele frequency",
            "population",
            "South Asian",
            "East Asian",
            "European",
            "Latino",
            "Hispanic",
            "Admixed American",
            "loss-of-function",
        ],
        citation_id="PA166169660", year=2023,
    ),
]

# --- PubMed Abstracts ---

PUBMED_DOCUMENTS: list[BiomedicalDocument] = [
    BiomedicalDocument(
        doc_id="pubmed_cyp2d6_sas",
        source=DocumentSource.PUBMED,
        title="CYP2D6 Allele Distribution in South Asian Populations",
        content=(
            "We characterized CYP2D6 allele frequencies in 2,500 South Asian individuals. "
            "The *4 allele (no function) was found at 9.2%, *41 (decreased function) at 11.8%, "
            "and *10 (decreased function) at 7.5%. The predicted intermediate metabolizer "
            "prevalence was 28%, higher than European populations. These findings highlight "
            "the need for population-specific pharmacogenomic guidelines."
        ),
        genes=["CYP2D6"], drugs=["codeine", "tamoxifen"],
        keywords=["South Asian", "allele frequency", "intermediate metabolizer", "population-specific"],
        citation_id="PMID:35891234", year=2023,
    ),
    BiomedicalDocument(
        doc_id="pubmed_hlab_sea",
        source=DocumentSource.PUBMED,
        title="HLA-B*15:02 Prevalence and Carbamazepine-Induced SJS in Southeast Asia",
        content=(
            "In a cohort of 5,000 Southeast Asian patients, HLA-B*15:02 prevalence was 8.1%. "
            "Among carbamazepine-treated patients, SJS/TEN occurred exclusively in *15:02 carriers "
            "(OR > 100). Pre-prescription genetic testing eliminated new SJS/TEN cases in the "
            "intervention group. Cost-effectiveness analysis supports universal testing in "
            "populations with >5% allele frequency."
        ),
        genes=["HLA-B"], drugs=["carbamazepine"],
        keywords=["SJS", "TEN", "Southeast Asian", "genetic testing", "cost-effectiveness"],
        citation_id="PMID:36123456", year=2023,
    ),
    BiomedicalDocument(
        # Hariprakash et al. — n>3000 South Asian DPYD landscape paper.
        # Required so that fluorouracil runs with population=SAS resolve
        # the POPULATION facet (otherwise the verifier fires V7 / R9
        # POPULATION UNCERTAIN and produces a soft-refusal). Surfaces the
        # rs2297595 enrichment finding so the recommendation text can
        # truthfully cite a SAS-specific source.
        doc_id="pubmed_dpyd_sas_landscape",
        source=DocumentSource.PUBMED,
        title="Pharmacogenetic Landscape of DPYD Variants in South Asian Populations",
        content=(
            "Systematic analysis of population-scale genome-wide datasets covering more than "
            "3,000 South Asian individuals revealed significant differences in the allelic "
            "distribution of DPYD variants relative to European reference panels. The CPIC "
            "canonical 4-variant European panel (c.1905+1G>A / *2A; c.1679T>G / *13; "
            "c.2846A>T; c.1129-5923C>G / HapB3) is calibrated against European cohorts and "
            "may underdetect carriers in South Asian populations. The normal-function variant "
            "rs2297595 (c.496A>G, p.Met166Val) is enriched in South Asia, and additional "
            "South-Asia-prevalent variants of potential clinical relevance to fluoropyrimidine "
            "toxicity are described. Findings argue for population-aware DPYD genotyping "
            "panels rather than uniform application of European-derived 4-variant panels in "
            "South Asian oncology populations. Hariprakash JM et al., 2018."
        ),
        genes=["DPYD"],
        drugs=["fluorouracil", "5-fluorouracil", "5-FU", "capecitabine"],
        keywords=[
            "South Asian",
            "Indian",
            "allele frequency",
            "population-specific",
            "rs2297595",
            "c.496A>G",
            "DPYD landscape",
            "panel coverage",
        ],
        citation_id="PMID:29239269", year=2018,
    ),
    BiomedicalDocument(
        # Chan & Pirmohamed 2024 systematic review — the non-European
        # equity anchor. Populates the POPULATION facet for SAS, EAS,
        # AFR, and AMR runs of fluorouracil so the runtime produces an
        # honest PASS_WITH_CAVEAT instead of a soft refusal. Names
        # c.557A>G (rs115232898) as the AFR-relevant decreased-function
        # variant the UK NHS 4-variant panel currently misses.
        doc_id="pubmed_dpyd_non_european",
        source=DocumentSource.PUBMED,
        title="DPYD Genetic Polymorphisms in Non-European Patients with Severe Fluoropyrimidine Toxicity",
        content=(
            "Systematic review of 53 DPYD variants reported in patients of non-European "
            "ancestry across five ethnic groups: African American, East Asian, Latin American, "
            "Middle Eastern, and South Asian. The European canonical no-function variant "
            "c.1905+1G>A (rs3918290 / *2A) is also present in South Asian, East Asian and "
            "Middle Eastern patients with severe fluoropyrimidine-related toxicity, although "
            "at much lower frequencies than in Europeans. The decreased-function variant "
            "c.557A>G (p.Tyr186Cys, rs115232898) is observed in individuals of African "
            "ancestry (~2.6% in African-heritage Brazilians) but is currently absent from the "
            "UK NHS 4-variant DPYD pre-treatment panel. Extending pre-treatment DPYD screening "
            "to include variants present in non-European ancestry groups is recommended to "
            "improve patient safety and reduce race-based health inequalities. Chan TH, "
            "Zhang JE, Pirmohamed M. Br J Cancer 2024;131(3):498-514."
        ),
        genes=["DPYD"],
        drugs=["fluorouracil", "5-fluorouracil", "5-FU", "capecitabine"],
        keywords=[
            "non-European",
            "South Asian",
            "East Asian",
            "African American",
            "African",
            "Latin American",
            "Latino",
            "Hispanic",
            "Admixed American",
            "Middle Eastern",
            "c.557A>G",
            "rs115232898",
            "panel coverage",
            "health equity",
            "systematic review",
        ],
        citation_id="PMID:38886557", year=2024,
    ),
]

ALL_DOCUMENTS = CPIC_DOCUMENTS + PHARMGKB_DOCUMENTS + PUBMED_DOCUMENTS
