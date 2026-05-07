"""Pharmacogene metadata — CYP2D6, CYP2C19, HLA-B.

Structured gene and allele records with provenance for the three
key pharmacogenes in the Anukriti Swarm demo pipeline.
"""

from __future__ import annotations

from biomedical.schemas import AlleleRecord, DataSource, GeneRecord, Provenance

_PHARMVAR = Provenance(source=DataSource.PHARMVAR, version="6.0.6")
_CPIC = Provenance(source=DataSource.CPIC, version="2023.1")

# --- Gene Records ---

GENES: dict[str, GeneRecord] = {
    "CYP2D6": GeneRecord(
        symbol="CYP2D6", chromosome="chr22",
        function="Phase I drug metabolism (oxidation). Metabolizes ~25% of clinically used drugs.",
        key_drugs=["codeine", "tamoxifen", "tramadol", "amitriptyline", "metoprolol"],
        key_alleles=["*1", "*2", "*4", "*5", "*10", "*17", "*41", "*1xN"],
        clinical_significance="Most polymorphic pharmacogene. PM/UM phenotypes have strong clinical impact.",
        provenance=_PHARMVAR,
    ),
    "CYP2C19": GeneRecord(
        symbol="CYP2C19", chromosome="chr10",
        function="Phase I drug metabolism. Critical for antiplatelet and PPI activation.",
        key_drugs=["clopidogrel", "omeprazole", "escitalopram", "voriconazole"],
        key_alleles=["*1", "*2", "*3", "*17"],
        clinical_significance="PM/IM phenotypes cause clopidogrel resistance — major cardiovascular risk.",
        provenance=_PHARMVAR,
    ),
    "HLA-B": GeneRecord(
        symbol="HLA-B", chromosome="chr6",
        function="Immune system antigen presentation. Specific alleles trigger severe ADRs.",
        key_drugs=["carbamazepine", "oxcarbazepine", "phenytoin", "abacavir"],
        key_alleles=["*15:02", "*57:01", "*58:01"],
        clinical_significance="*15:02 carriers: carbamazepine contraindicated (SJS/TEN risk >100x).",
        provenance=_CPIC,
    ),
}

# --- Allele Records ---

ALLELES: dict[str, list[AlleleRecord]] = {
    "CYP2D6": [
        AlleleRecord("CYP2D6", "*1", "normal_function", 1.0, [], "Reference allele", _PHARMVAR),
        AlleleRecord("CYP2D6", "*2", "normal_function", 1.0, ["rs16947"], "Normal function variant", _PHARMVAR),
        AlleleRecord("CYP2D6", "*4", "no_function", 0.0, ["rs3892097"], "Most common null allele (EUR)", _PHARMVAR),
        AlleleRecord("CYP2D6", "*5", "no_function", 0.0, [], "Gene deletion", _PHARMVAR),
        AlleleRecord("CYP2D6", "*10", "decreased_function", 0.5, ["rs1065852"], "Common in EAS", _PHARMVAR),
        AlleleRecord("CYP2D6", "*17", "decreased_function", 0.5, ["rs28371706"], "Common in AFR", _PHARMVAR),
        AlleleRecord("CYP2D6", "*41", "decreased_function", 0.5, ["rs28371725"], "Decreased function", _PHARMVAR),
        AlleleRecord("CYP2D6", "*1xN", "increased_function", 2.0, [], "Gene duplication (UM risk)", _PHARMVAR),
    ],
    "CYP2C19": [
        AlleleRecord("CYP2C19", "*1", "normal_function", 1.0, [], "Reference allele", _PHARMVAR),
        AlleleRecord("CYP2C19", "*2", "no_function", 0.0, ["rs4244285"], "Most common LOF globally", _PHARMVAR),
        AlleleRecord("CYP2C19", "*3", "no_function", 0.0, ["rs4986893"], "LOF, primarily EAS", _PHARMVAR),
        AlleleRecord("CYP2C19", "*17", "increased_function", 1.5, ["rs12248560"], "Gain-of-function", _PHARMVAR),
    ],
    "HLA-B": [
        AlleleRecord("HLA-B", "*15:02", "risk_allele", 0.0, ["rs2395029"], "SJS/TEN risk with carbamazepine", _CPIC),
        AlleleRecord("HLA-B", "*57:01", "risk_allele", 0.0, [], "Abacavir hypersensitivity", _CPIC),
        AlleleRecord("HLA-B", "*58:01", "risk_allele", 0.0, [], "Allopurinol hypersensitivity", _CPIC),
    ],
}
