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
        keywords=["allele frequency", "population", "South Asian", "East Asian", "loss-of-function"],
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
]

ALL_DOCUMENTS = CPIC_DOCUMENTS + PHARMGKB_DOCUMENTS + PUBMED_DOCUMENTS
