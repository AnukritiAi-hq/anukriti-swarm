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

# GenomeIndia public summary stats are aggregate Indian allele frequencies,
# not gnomAD-style super-pop strata. Keep this map separate so the ingestion
# script can include Indian/DPYD audit variants without changing the gnomAD
# BigQuery query surface.
GENOMEINDIA_VARIANTS: dict[str, tuple[str, str, str]] = {
    **PGX_VARIANTS,
    "rs55886062": ("DPYD", "*13", "no_function"),
    "rs75017182": ("DPYD", "c.1129-5923C>G", "decreased_function"),
    "rs115232898": ("DPYD", "Y186C", "decreased_function"),
    "rs1801265": ("DPYD", "*9A", "normal_function"),
    "rs1801160": ("DPYD", "*6", "normal_function"),
    "rs2297595": ("DPYD", "M166V", "normal_function"),
}

# GRCh38/NC_000001.11-style plus-strand coordinates for public GenomeIndia
# summary stats, whose ID field is ".". Values are (chrom, pos, ref, alt).
#
# CYP2C19/CYP2C9/SLCO1B1 positions are GRCh38 plus-strand positions verified
# against PharmGKB/GeneWizard/SNPedia and the focused GenomeIndia extract.
# DPYD positions are from CPIC/AMP/CAP/PharmVar-aligned GRCh38 tables and
# ClinVar/ClinGen records, matching the plus-strand REF/ALT convention used by
# pgx-core.
GENOMEINDIA_VARIANT_COORDS: dict[str, tuple[str, int, str, str]] = {
    "rs4244285": ("10", 94781859, "G", "A"),
    "rs12248560": ("10", 94761900, "C", "T"),
    "rs1799853": ("10", 94942290, "C", "T"),
    "rs1057910": ("10", 94981296, "A", "C"),
    "rs9923231": ("16", 31096368, "C", "T"),
    "rs4149056": ("12", 21178615, "T", "C"),
    "rs3918290": ("1", 97450058, "C", "T"),
    "rs55886062": ("1", 97515787, "A", "C"),
    "rs67376798": ("1", 97082391, "T", "A"),
    "rs56038477": ("1", 97573863, "C", "T"),
    "rs75017182": ("1", 97579893, "G", "C"),
    "rs115232898": ("1", 97699474, "T", "C"),
    "rs1801265": ("1", 97883329, "A", "G"),
    "rs1801160": ("1", 97305364, "C", "T"),
    "rs2297595": ("1", 97699535, "T", "C"),
}

# gnomAD v2.1.1 subpop -> Anukriti superpopulation
GNOMAD_POP_MAP: dict[str, str] = {
    "afr": "AFR", "amr": "AMR", "eas": "EAS", "sas": "SAS", "nfe": "EUR",
}
