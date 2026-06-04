"""rsID -> (gene, star-allele, function) map for gnomAD ingestion.

Maps the CPIC Level-A PGx defining variants to the allele label and
function vocabulary used by AlleleFrequencyRecord. Used only by the
offline ingestion script (scripts/ingest_gnomad_frequencies.py) to tag
real gnomAD allele frequencies — never imported at reasoning time.
"""

from __future__ import annotations

# rsid: (gene, allele_label, function)
PGX_VARIANTS: dict[str, tuple[str, str, str]] = {
    "rs3892097": ("CYP2D6", "*4", "no_function"),
    "rs1065852": ("CYP2D6", "*10", "decreased_function"),
    "rs28371706": ("CYP2D6", "*17", "decreased_function"),
    "rs4244285": ("CYP2C19", "*2", "no_function"),
    "rs4986893": ("CYP2C19", "*3", "no_function"),
    "rs12248560": ("CYP2C19", "*17", "increased_function"),
    "rs1799853": ("CYP2C9", "*2", "decreased_function"),
    "rs1057910": ("CYP2C9", "*3", "no_function"),
    "rs4149056": ("SLCO1B1", "*5", "decreased_function"),
    "rs9923231": ("VKORC1", "A", "decreased_function"),
    "rs1800462": ("TPMT", "*2", "no_function"),
    "rs1800460": ("TPMT", "*3B", "no_function"),
    "rs1142345": ("TPMT", "*3C", "no_function"),
    "rs3918290": ("DPYD", "*2A", "no_function"),
    "rs67376798": ("DPYD", "c.2846A>T", "decreased_function"),
    "rs56038477": ("DPYD", "HapB3", "decreased_function"),
    "rs1801280": ("NAT2", "*5", "decreased_function"),
    "rs1799930": ("NAT2", "*6", "decreased_function"),
    "rs1799931": ("NAT2", "*7", "decreased_function"),
    "rs3745274": ("CYP2B6", "*6", "decreased_function"),
    "rs762551": ("CYP1A2", "*1F", "increased_function"),
    "rs776746": ("CYP3A5", "*3", "no_function"),
    "rs1050828": ("G6PD", "A-", "decreased_function"),
    "rs5030868": ("G6PD", "Mediterranean", "no_function"),
}

# gnomAD v2.1.1 subpop -> Anukriti superpopulation
GNOMAD_POP_MAP: dict[str, str] = {
    "afr": "AFR", "amr": "AMR", "eas": "EAS", "sas": "SAS", "nfe": "EUR",
}
