"""Anukriti Swarm — Mock genomic data fixtures.

Provides realistic mock data for testing the orchestration pipeline
without requiring real genomic databases or VCF files.

Data is based on well-known pharmacogenomic examples:
- CYP2D6 *1/*4 (intermediate metabolizer, codeine/tamoxifen)
- CYP2C19 *1/*2 (intermediate metabolizer, clopidogrel)
"""

from __future__ import annotations

from agents.models import PharmacogeneResult, PopulationContext, VariantRecord

# --- Mock VCF Variants ---

MOCK_VARIANTS_CYP2D6: list[VariantRecord] = [
    VariantRecord(
        chromosome="chr22",
        position=42128945,
        ref_allele="C",
        alt_allele="T",
        gene="CYP2D6",
        rsid="rs3892097",
        quality=99.0,
    ),
]

MOCK_VARIANTS_CYP2C19: list[VariantRecord] = [
    VariantRecord(
        chromosome="chr10",
        position=94781859,
        ref_allele="G",
        alt_allele="A",
        gene="CYP2C19",
        rsid="rs4244285",
        quality=98.0,
    ),
]

MOCK_VARIANTS_HLA: list[VariantRecord] = [
    VariantRecord(
        chromosome="chr6",
        position=31356526,
        ref_allele="A",
        alt_allele="G",
        gene="HLA-B",
        rsid="rs2395029",
        quality=95.0,
    ),
]

ALL_MOCK_VARIANTS = MOCK_VARIANTS_CYP2D6 + MOCK_VARIANTS_CYP2C19 + MOCK_VARIANTS_HLA

# --- Mock Pharmacogene Results ---

MOCK_PHARMACOGENE_CYP2D6 = PharmacogeneResult(
    gene="CYP2D6",
    diplotype="*1/*4",
    phenotype="Intermediate Metabolizer",
    drugs_affected=["codeine", "tamoxifen", "tramadol", "amitriptyline"],
    guideline_source="CPIC:CYP2D6:2023",
    confidence=1.0,
)

MOCK_PHARMACOGENE_CYP2C19 = PharmacogeneResult(
    gene="CYP2C19",
    diplotype="*1/*2",
    phenotype="Intermediate Metabolizer",
    drugs_affected=["clopidogrel", "omeprazole", "escitalopram"],
    guideline_source="CPIC:CYP2C19:2022",
    confidence=1.0,
)

# --- Mock Population Frequencies ---

MOCK_POPULATION_SAS: dict[str, PopulationContext] = {
    "CYP2D6*4": PopulationContext(
        population="SAS", allele_frequency=0.09, frequency_source="gnomAD v4.0", is_common=True
    ),
    "CYP2C19*2": PopulationContext(
        population="SAS", allele_frequency=0.36, frequency_source="gnomAD v4.0", is_common=True
    ),
}

MOCK_POPULATION_EUR: dict[str, PopulationContext] = {
    "CYP2D6*4": PopulationContext(
        population="EUR", allele_frequency=0.22, frequency_source="gnomAD v4.0", is_common=True
    ),
    "CYP2C19*2": PopulationContext(
        population="EUR", allele_frequency=0.15, frequency_source="gnomAD v4.0", is_common=True
    ),
}

MOCK_POPULATION_AFR: dict[str, PopulationContext] = {
    "CYP2D6*4": PopulationContext(
        population="AFR", allele_frequency=0.02, frequency_source="gnomAD v4.0", is_common=True
    ),
    "CYP2C19*2": PopulationContext(
        population="AFR", allele_frequency=0.18, frequency_source="gnomAD v4.0", is_common=True
    ),
}

# --- Mock Evidence ---

MOCK_EVIDENCE = [
    {
        "gene": "CYP2D6",
        "source": "PMID:32722396",
        "title": "CPIC Guideline for CYP2D6 and Codeine Therapy",
        "passage": "Intermediate metabolizers have reduced morphine formation from codeine. "
        "Consider alternative analgesics.",
        "relevance_score": 0.95,
    },
    {
        "gene": "CYP2C19",
        "source": "PMID:34032273",
        "title": "CPIC Guideline for CYP2C19 and Clopidogrel Therapy",
        "passage": "Intermediate metabolizers have reduced platelet inhibition. "
        "Consider alternative antiplatelet therapy.",
        "relevance_score": 0.93,
    },
]
