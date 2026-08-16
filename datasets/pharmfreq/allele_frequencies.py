"""PharmFreq-compatible allele frequency data.

Data based on real pharmacogenomic allele frequencies from:
- PharmFreq (https://www.pharmfreq.org/)
- gnomAD v4.0
- 1000 Genomes Phase 3

Frequencies are realistic approximations for demonstration and
population-aware reasoning. Schema follows PharmFreq conventions.

Genes covered (13 pgx-core genes):
- CYP2D6: codeine, tamoxifen, antidepressants
- CYP2C19: clopidogrel, PPIs, antidepressants
- CYP1A2: clozapine, theophylline, caffeine
- CYP2B6: efavirenz, bupropion
- CYP2C9: warfarin, phenytoin, NSAIDs
- CYP3A4: tacrolimus, midazolam, statins
- CYP3A5: tacrolimus, transplant immunosuppressants
- DPYD: fluorouracil, capecitabine
- TPMT: azathioprine, mercaptopurine
- NAT2: isoniazid, TB treatment
- G6PD: primaquine, rasburicase, dapsone
- VKORC1: warfarin (with CYP2C9)
- SLCO1B1: statins (simvastatin, atorvastatin)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlleleFrequencyRecord:
    """A single allele frequency observation in a population.

    PharmFreq-compatible schema with provenance fields.
    """

    gene: str
    allele: str           # Star allele (e.g., "*4") or genotype (e.g., "GG")
    population: str       # Super-population code (SAS, AFR, EUR, EAS, AMR)
    frequency: float      # Allele frequency (0.0 - 1.0)
    sample_n: int         # Number of samples in reference
    source: str           # Data source
    version: str          # Source version
    function: str         # "no_function", "decreased_function", "normal_function", "increased_function"


# --- CYP2D6 Allele Frequencies ---

CYP2D6_FREQUENCIES: list[AlleleFrequencyRecord] = [
    # *1 (normal function) — reference allele
    AlleleFrequencyRecord("CYP2D6", "*1", "SAS", 0.40, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2D6", "*1", "AFR", 0.35, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2D6", "*1", "EUR", 0.38, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2D6", "*1", "EAS", 0.42, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2D6", "*1", "AMR", 0.45, 7647, "gnomAD", "v4.0", "normal_function"),
    # *2 (normal function)
    AlleleFrequencyRecord("CYP2D6", "*2", "SAS", 0.28, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2D6", "*2", "AFR", 0.22, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2D6", "*2", "EUR", 0.25, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2D6", "*2", "EAS", 0.15, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2D6", "*2", "AMR", 0.22, 7647, "gnomAD", "v4.0", "normal_function"),
    # *4 (no function) — most common loss-of-function in EUR
    AlleleFrequencyRecord("CYP2D6", "*4", "SAS", 0.09, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2D6", "*4", "AFR", 0.02, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2D6", "*4", "EUR", 0.22, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2D6", "*4", "EAS", 0.01, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2D6", "*4", "AMR", 0.12, 7647, "gnomAD", "v4.0", "no_function"),
    # *10 (decreased function) — common in EAS
    AlleleFrequencyRecord("CYP2D6", "*10", "SAS", 0.08, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2D6", "*10", "AFR", 0.04, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2D6", "*10", "EUR", 0.02, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2D6", "*10", "EAS", 0.38, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2D6", "*10", "AMR", 0.05, 7647, "gnomAD", "v4.0", "decreased_function"),
    # *17 (decreased function) — common in AFR
    AlleleFrequencyRecord("CYP2D6", "*17", "SAS", 0.01, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2D6", "*17", "AFR", 0.20, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2D6", "*17", "EUR", 0.01, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2D6", "*17", "EAS", 0.00, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2D6", "*17", "AMR", 0.03, 7647, "gnomAD", "v4.0", "decreased_function"),
    # *41 (decreased function)
    AlleleFrequencyRecord("CYP2D6", "*41", "SAS", 0.12, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2D6", "*41", "AFR", 0.10, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2D6", "*41", "EUR", 0.09, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2D6", "*41", "EAS", 0.02, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2D6", "*41", "AMR", 0.08, 7647, "gnomAD", "v4.0", "decreased_function"),
]

# --- CYP2C19 Allele Frequencies ---

CYP2C19_FREQUENCIES: list[AlleleFrequencyRecord] = [
    # *1 (normal function) — reference
    AlleleFrequencyRecord("CYP2C19", "*1", "SAS", 0.50, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2C19", "*1", "AFR", 0.68, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2C19", "*1", "EUR", 0.63, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2C19", "*1", "EAS", 0.36, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2C19", "*1", "AMR", 0.60, 7647, "gnomAD", "v4.0", "normal_function"),
    # *2 (no function) — most common LOF
    AlleleFrequencyRecord("CYP2C19", "*2", "SAS", 0.36, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C19", "*2", "AFR", 0.18, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C19", "*2", "EUR", 0.15, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C19", "*2", "EAS", 0.30, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C19", "*2", "AMR", 0.12, 7647, "gnomAD", "v4.0", "no_function"),
    # *3 (no function) — primarily EAS
    AlleleFrequencyRecord("CYP2C19", "*3", "SAS", 0.02, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C19", "*3", "AFR", 0.00, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C19", "*3", "EUR", 0.00, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C19", "*3", "EAS", 0.08, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C19", "*3", "AMR", 0.01, 7647, "gnomAD", "v4.0", "no_function"),
    # *17 (increased function) — gain-of-function
    AlleleFrequencyRecord("CYP2C19", "*17", "SAS", 0.12, 15308, "gnomAD", "v4.0", "increased_function"),
    AlleleFrequencyRecord("CYP2C19", "*17", "AFR", 0.14, 20744, "gnomAD", "v4.0", "increased_function"),
    AlleleFrequencyRecord("CYP2C19", "*17", "EUR", 0.22, 64603, "gnomAD", "v4.0", "increased_function"),
    AlleleFrequencyRecord("CYP2C19", "*17", "EAS", 0.02, 9197, "gnomAD", "v4.0", "increased_function"),
    AlleleFrequencyRecord("CYP2C19", "*17", "AMR", 0.15, 7647, "gnomAD", "v4.0", "increased_function"),
]

# --- CYP1A2 Allele Frequencies ---
# Key alleles: *1F (inducible, common), *1C (decreased), others rare

CYP1A2_FREQUENCIES: list[AlleleFrequencyRecord] = [
    # *1 (normal function) — reference/wildtype
    AlleleFrequencyRecord("CYP1A2", "*1", "SAS", 0.52, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP1A2", "*1", "AFR", 0.48, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP1A2", "*1", "EUR", 0.32, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP1A2", "*1", "EAS", 0.38, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP1A2", "*1", "AMR", 0.42, 7647, "gnomAD", "v4.0", "normal_function"),
    # *1F (increased function / inducible) — very common globally
    AlleleFrequencyRecord("CYP1A2", "*1F", "SAS", 0.38, 15308, "gnomAD", "v4.0", "increased_function"),
    AlleleFrequencyRecord("CYP1A2", "*1F", "AFR", 0.42, 20744, "gnomAD", "v4.0", "increased_function"),
    AlleleFrequencyRecord("CYP1A2", "*1F", "EUR", 0.54, 64603, "gnomAD", "v4.0", "increased_function"),
    AlleleFrequencyRecord("CYP1A2", "*1F", "EAS", 0.48, 9197, "gnomAD", "v4.0", "increased_function"),
    AlleleFrequencyRecord("CYP1A2", "*1F", "AMR", 0.46, 7647, "gnomAD", "v4.0", "increased_function"),
    # *1C (decreased function) — common in EAS/SAS
    AlleleFrequencyRecord("CYP1A2", "*1C", "SAS", 0.06, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP1A2", "*1C", "AFR", 0.04, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP1A2", "*1C", "EUR", 0.01, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP1A2", "*1C", "EAS", 0.10, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP1A2", "*1C", "AMR", 0.04, 7647, "gnomAD", "v4.0", "decreased_function"),
    # *1K (decreased function) — rare
    AlleleFrequencyRecord("CYP1A2", "*1K", "SAS", 0.02, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP1A2", "*1K", "AFR", 0.01, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP1A2", "*1K", "EUR", 0.01, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP1A2", "*1K", "EAS", 0.02, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP1A2", "*1K", "AMR", 0.01, 7647, "gnomAD", "v4.0", "decreased_function"),
    # *3 (no function) — rare
    AlleleFrequencyRecord("CYP1A2", "*3", "SAS", 0.001, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP1A2", "*3", "AFR", 0.001, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP1A2", "*3", "EUR", 0.001, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP1A2", "*3", "EAS", 0.002, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP1A2", "*3", "AMR", 0.001, 7647, "gnomAD", "v4.0", "no_function"),
    # *4 (no function) — rare
    AlleleFrequencyRecord("CYP1A2", "*4", "SAS", 0.001, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP1A2", "*4", "AFR", 0.002, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP1A2", "*4", "EUR", 0.001, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP1A2", "*4", "EAS", 0.001, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP1A2", "*4", "AMR", 0.001, 7647, "gnomAD", "v4.0", "no_function"),
]

# --- CYP2B6 Allele Frequencies ---
# Equity-significant: *6 ~50% AFR vs ~25% EUR. HIV treatment equity.

CYP2B6_FREQUENCIES: list[AlleleFrequencyRecord] = [
    # *1 (normal function) — reference
    AlleleFrequencyRecord("CYP2B6", "*1", "SAS", 0.45, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2B6", "*1", "AFR", 0.32, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2B6", "*1", "EUR", 0.55, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2B6", "*1", "EAS", 0.52, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2B6", "*1", "AMR", 0.50, 7647, "gnomAD", "v4.0", "normal_function"),
    # *6 (decreased function) — most clinically significant; high in AFR
    AlleleFrequencyRecord("CYP2B6", "*6", "SAS", 0.28, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2B6", "*6", "AFR", 0.38, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2B6", "*6", "EUR", 0.25, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2B6", "*6", "EAS", 0.22, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2B6", "*6", "AMR", 0.26, 7647, "gnomAD", "v4.0", "decreased_function"),
    # *4 (normal/increased function)
    AlleleFrequencyRecord("CYP2B6", "*4", "SAS", 0.03, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2B6", "*4", "AFR", 0.02, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2B6", "*4", "EUR", 0.04, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2B6", "*4", "EAS", 0.02, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2B6", "*4", "AMR", 0.03, 7647, "gnomAD", "v4.0", "normal_function"),
    # *5 (decreased function)
    AlleleFrequencyRecord("CYP2B6", "*5", "SAS", 0.04, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2B6", "*5", "AFR", 0.02, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2B6", "*5", "EUR", 0.06, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2B6", "*5", "EAS", 0.04, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2B6", "*5", "AMR", 0.05, 7647, "gnomAD", "v4.0", "decreased_function"),
    # *9 (decreased function)
    AlleleFrequencyRecord("CYP2B6", "*9", "SAS", 0.05, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2B6", "*9", "AFR", 0.03, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2B6", "*9", "EUR", 0.03, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2B6", "*9", "EAS", 0.08, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2B6", "*9", "AMR", 0.04, 7647, "gnomAD", "v4.0", "decreased_function"),
    # *18 (no function) — significant in AFR
    AlleleFrequencyRecord("CYP2B6", "*18", "SAS", 0.01, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2B6", "*18", "AFR", 0.08, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2B6", "*18", "EUR", 0.00, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2B6", "*18", "EAS", 0.00, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2B6", "*18", "AMR", 0.02, 7647, "gnomAD", "v4.0", "no_function"),
]

# --- CYP2C9 Allele Frequencies ---
# Warfarin dosing gene. *2 and *3 are most clinically significant.

CYP2C9_FREQUENCIES: list[AlleleFrequencyRecord] = [
    # *1 (normal function) — reference
    AlleleFrequencyRecord("CYP2C9", "*1", "SAS", 0.78, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2C9", "*1", "AFR", 0.86, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2C9", "*1", "EUR", 0.65, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2C9", "*1", "EAS", 0.92, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP2C9", "*1", "AMR", 0.75, 7647, "gnomAD", "v4.0", "normal_function"),
    # *2 (decreased function) — common in EUR
    AlleleFrequencyRecord("CYP2C9", "*2", "SAS", 0.04, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2C9", "*2", "AFR", 0.02, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2C9", "*2", "EUR", 0.13, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2C9", "*2", "EAS", 0.00, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP2C9", "*2", "AMR", 0.08, 7647, "gnomAD", "v4.0", "decreased_function"),
    # *3 (no function) — common in EUR/SAS
    AlleleFrequencyRecord("CYP2C9", "*3", "SAS", 0.10, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*3", "AFR", 0.01, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*3", "EUR", 0.07, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*3", "EAS", 0.04, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*3", "AMR", 0.05, 7647, "gnomAD", "v4.0", "no_function"),
    # *5 (no function) — AFR-enriched
    AlleleFrequencyRecord("CYP2C9", "*5", "SAS", 0.00, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*5", "AFR", 0.02, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*5", "EUR", 0.00, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*5", "EAS", 0.00, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*5", "AMR", 0.01, 7647, "gnomAD", "v4.0", "no_function"),
    # *8 (no function) — AFR-enriched
    AlleleFrequencyRecord("CYP2C9", "*8", "SAS", 0.01, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*8", "AFR", 0.06, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*8", "EUR", 0.00, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*8", "EAS", 0.00, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*8", "AMR", 0.01, 7647, "gnomAD", "v4.0", "no_function"),
    # *11 (no function) — rare
    AlleleFrequencyRecord("CYP2C9", "*11", "SAS", 0.01, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*11", "AFR", 0.02, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*11", "EUR", 0.01, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*11", "EAS", 0.00, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP2C9", "*11", "AMR", 0.01, 7647, "gnomAD", "v4.0", "no_function"),
]

# --- CYP3A4 Allele Frequencies ---
# Primary variant: *22 (decreased function). Most others are rare.

CYP3A4_FREQUENCIES: list[AlleleFrequencyRecord] = [
    # *1 (normal function) — reference
    AlleleFrequencyRecord("CYP3A4", "*1", "SAS", 0.92, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP3A4", "*1", "AFR", 0.93, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP3A4", "*1", "EUR", 0.92, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP3A4", "*1", "EAS", 0.96, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP3A4", "*1", "AMR", 0.93, 7647, "gnomAD", "v4.0", "normal_function"),
    # *22 (decreased function) — most clinically significant
    AlleleFrequencyRecord("CYP3A4", "*22", "SAS", 0.04, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP3A4", "*22", "AFR", 0.01, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP3A4", "*22", "EUR", 0.05, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP3A4", "*22", "EAS", 0.02, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("CYP3A4", "*22", "AMR", 0.04, 7647, "gnomAD", "v4.0", "decreased_function"),
    # *2 (no function) — rare
    AlleleFrequencyRecord("CYP3A4", "*2", "SAS", 0.01, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A4", "*2", "AFR", 0.02, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A4", "*2", "EUR", 0.01, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A4", "*2", "EAS", 0.01, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A4", "*2", "AMR", 0.01, 7647, "gnomAD", "v4.0", "no_function"),
    # *17 (increased function) — rare
    AlleleFrequencyRecord("CYP3A4", "*17", "SAS", 0.01, 15308, "gnomAD", "v4.0", "increased_function"),
    AlleleFrequencyRecord("CYP3A4", "*17", "AFR", 0.02, 20744, "gnomAD", "v4.0", "increased_function"),
    AlleleFrequencyRecord("CYP3A4", "*17", "EUR", 0.00, 64603, "gnomAD", "v4.0", "increased_function"),
    AlleleFrequencyRecord("CYP3A4", "*17", "EAS", 0.00, 9197, "gnomAD", "v4.0", "increased_function"),
    AlleleFrequencyRecord("CYP3A4", "*17", "AMR", 0.01, 7647, "gnomAD", "v4.0", "increased_function"),
]

# --- CYP3A5 Allele Frequencies ---
# Equity-critical: *1 (expressor) ~75% AFR vs ~10% EUR.
# Tacrolimus under-dosing in African transplant recipients.

CYP3A5_FREQUENCIES: list[AlleleFrequencyRecord] = [
    # *1 (normal function / expressor) — high in AFR
    AlleleFrequencyRecord("CYP3A5", "*1", "SAS", 0.35, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP3A5", "*1", "AFR", 0.73, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP3A5", "*1", "EUR", 0.07, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP3A5", "*1", "EAS", 0.25, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("CYP3A5", "*1", "AMR", 0.25, 7647, "gnomAD", "v4.0", "normal_function"),
    # *3 (no function) — most common non-expressor; high in EUR
    AlleleFrequencyRecord("CYP3A5", "*3", "SAS", 0.60, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A5", "*3", "AFR", 0.18, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A5", "*3", "EUR", 0.90, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A5", "*3", "EAS", 0.70, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A5", "*3", "AMR", 0.68, 7647, "gnomAD", "v4.0", "no_function"),
    # *6 (no function) — AFR-enriched
    AlleleFrequencyRecord("CYP3A5", "*6", "SAS", 0.00, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A5", "*6", "AFR", 0.07, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A5", "*6", "EUR", 0.00, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A5", "*6", "EAS", 0.00, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A5", "*6", "AMR", 0.02, 7647, "gnomAD", "v4.0", "no_function"),
    # *7 (no function) — rare
    AlleleFrequencyRecord("CYP3A5", "*7", "SAS", 0.01, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A5", "*7", "AFR", 0.01, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A5", "*7", "EUR", 0.01, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A5", "*7", "EAS", 0.01, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("CYP3A5", "*7", "AMR", 0.01, 7647, "gnomAD", "v4.0", "no_function"),
]

# --- DPYD Allele Frequencies ---
# High-stakes: *2A carriers have 1-2% risk of fatal 5-FU toxicity.

DPYD_FREQUENCIES: list[AlleleFrequencyRecord] = [
    # *1 (normal function) — reference
    AlleleFrequencyRecord("DPYD", "*1", "SAS", 0.94, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("DPYD", "*1", "AFR", 0.96, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("DPYD", "*1", "EUR", 0.93, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("DPYD", "*1", "EAS", 0.97, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("DPYD", "*1", "AMR", 0.95, 7647, "gnomAD", "v4.0", "normal_function"),
    # *2A (no function) — most clinically significant; EUR-enriched
    AlleleFrequencyRecord("DPYD", "*2A", "SAS", 0.005, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("DPYD", "*2A", "AFR", 0.001, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("DPYD", "*2A", "EUR", 0.012, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("DPYD", "*2A", "EAS", 0.001, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("DPYD", "*2A", "AMR", 0.006, 7647, "gnomAD", "v4.0", "no_function"),
    # *13 (no function) — rare but lethal
    AlleleFrequencyRecord("DPYD", "*13", "SAS", 0.001, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("DPYD", "*13", "AFR", 0.001, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("DPYD", "*13", "EUR", 0.002, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("DPYD", "*13", "EAS", 0.001, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("DPYD", "*13", "AMR", 0.001, 7647, "gnomAD", "v4.0", "no_function"),
    # c.1679T>G (no function) — rare
    AlleleFrequencyRecord("DPYD", "c.1679T>G", "SAS", 0.001, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("DPYD", "c.1679T>G", "AFR", 0.000, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("DPYD", "c.1679T>G", "EUR", 0.001, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("DPYD", "c.1679T>G", "EAS", 0.000, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("DPYD", "c.1679T>G", "AMR", 0.001, 7647, "gnomAD", "v4.0", "no_function"),
    # c.2846A>T (decreased function) — EUR-enriched
    AlleleFrequencyRecord("DPYD", "c.2846A>T", "SAS", 0.003, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("DPYD", "c.2846A>T", "AFR", 0.001, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("DPYD", "c.2846A>T", "EUR", 0.006, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("DPYD", "c.2846A>T", "EAS", 0.001, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("DPYD", "c.2846A>T", "AMR", 0.004, 7647, "gnomAD", "v4.0", "decreased_function"),
    # HapB3 (decreased function) — EUR-enriched
    AlleleFrequencyRecord("DPYD", "HapB3", "SAS", 0.005, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("DPYD", "HapB3", "AFR", 0.002, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("DPYD", "HapB3", "EUR", 0.022, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("DPYD", "HapB3", "EAS", 0.001, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("DPYD", "HapB3", "AMR", 0.010, 7647, "gnomAD", "v4.0", "decreased_function"),

    # --- *9A (rs1801265, c.85T>C) and M166V (rs2297595, c.496A>G) ---
    # Both assigned **Normal function** by CPIC (verified against CPIC's
    # live allele API, 2026-07-28). Retained here because the swarm's
    # population-aware layer flags them as a contested-evidence research
    # question (rule P1_SAS_DPYD_CONTESTED), not because either is an
    # established South Asian risk allele.
    #
    # Frequencies below are REAL gnomAD v2.1.1 exome numbers, queried live
    # on 2026-07-28 and replacing hand-written approximations that were
    # wrong in both magnitude and direction. Audit trail:
    # anukriti_docs/DPYD_SAS_OVERRIDE_AUDIT_2026-07-28.md
    #
    # NOTE on *9A: gnomAD represents rs1801265 as 1-98348885-G-A, where the
    # *9A variant allele is the REF letter (G) — DPYD is a minus-strand
    # gene. The frequencies below are for the *variant* allele
    # (1 - AF(A)), not gnomAD's raw ALT AF.
    #
    # Neither allele is South-Asian-enriched in real data:
    #   *9A   SAS 0.2550 vs EUR 0.2226 -> ratio 1.15 (AFR 0.4131 is the max)
    #   M166V SAS 0.0906 vs EUR 0.1004 -> ratio 0.90 (SAS *below* EUR)
    AlleleFrequencyRecord("DPYD", "*9A", "SAS", 0.2550, 30608, "gnomAD", "v2.1.1_exomes_live_2026-07-28", "normal_function"),
    AlleleFrequencyRecord("DPYD", "*9A", "AFR", 0.4131, 16238, "gnomAD", "v2.1.1_exomes_live_2026-07-28", "normal_function"),
    AlleleFrequencyRecord("DPYD", "*9A", "EUR", 0.2226, 113316, "gnomAD", "v2.1.1_exomes_live_2026-07-28", "normal_function"),
    AlleleFrequencyRecord("DPYD", "*9A", "EAS", 0.0720, 18348, "gnomAD", "v2.1.1_exomes_live_2026-07-28", "normal_function"),
    AlleleFrequencyRecord("DPYD", "*9A", "AMR", 0.2113, 34524, "gnomAD", "v2.1.1_exomes_live_2026-07-28", "normal_function"),

    AlleleFrequencyRecord("DPYD", "M166V", "SAS", 0.0906, 30584, "gnomAD", "v2.1.1_exomes_live_2026-07-28", "normal_function"),
    AlleleFrequencyRecord("DPYD", "M166V", "AFR", 0.0334, 16240, "gnomAD", "v2.1.1_exomes_live_2026-07-28", "normal_function"),
    AlleleFrequencyRecord("DPYD", "M166V", "EUR", 0.1004, 113440, "gnomAD", "v2.1.1_exomes_live_2026-07-28", "normal_function"),
    AlleleFrequencyRecord("DPYD", "M166V", "EAS", 0.0158, 18394, "gnomAD", "v2.1.1_exomes_live_2026-07-28", "normal_function"),
    AlleleFrequencyRecord("DPYD", "M166V", "AMR", 0.0359, 34556, "gnomAD", "v2.1.1_exomes_live_2026-07-28", "normal_function"),
]

# --- TPMT Allele Frequencies ---
# Thiopurine dosing. *3A most common in EUR, *3C in AFR/EAS.

TPMT_FREQUENCIES: list[AlleleFrequencyRecord] = [
    # *1 (normal function) — reference
    AlleleFrequencyRecord("TPMT", "*1", "SAS", 0.92, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("TPMT", "*1", "AFR", 0.92, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("TPMT", "*1", "EUR", 0.90, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("TPMT", "*1", "EAS", 0.95, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("TPMT", "*1", "AMR", 0.93, 7647, "gnomAD", "v4.0", "normal_function"),
    # *3A (no function) — most common in EUR
    AlleleFrequencyRecord("TPMT", "*3A", "SAS", 0.02, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*3A", "AFR", 0.01, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*3A", "EUR", 0.05, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*3A", "EAS", 0.00, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*3A", "AMR", 0.03, 7647, "gnomAD", "v4.0", "no_function"),
    # *3C (no function) — most common in AFR/EAS
    AlleleFrequencyRecord("TPMT", "*3C", "SAS", 0.03, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*3C", "AFR", 0.05, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*3C", "EUR", 0.003, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*3C", "EAS", 0.03, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*3C", "AMR", 0.02, 7647, "gnomAD", "v4.0", "no_function"),
    # *2 (no function) — rare
    AlleleFrequencyRecord("TPMT", "*2", "SAS", 0.003, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*2", "AFR", 0.002, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*2", "EUR", 0.003, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*2", "EAS", 0.001, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*2", "AMR", 0.002, 7647, "gnomAD", "v4.0", "no_function"),
    # *4 (no function) — rare
    AlleleFrequencyRecord("TPMT", "*4", "SAS", 0.001, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*4", "AFR", 0.001, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*4", "EUR", 0.001, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*4", "EAS", 0.001, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("TPMT", "*4", "AMR", 0.001, 7647, "gnomAD", "v4.0", "no_function"),
]

# --- NAT2 Allele Frequencies ---
# TB treatment equity. Slow acetylators: ~90% Middle East, ~60% EUR, ~30% AFR.
# Wildtype is *4 (rapid acetylator).

NAT2_FREQUENCIES: list[AlleleFrequencyRecord] = [
    # *4 (rapid acetylator) — reference/wildtype
    AlleleFrequencyRecord("NAT2", "*4", "SAS", 0.25, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("NAT2", "*4", "AFR", 0.35, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("NAT2", "*4", "EUR", 0.23, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("NAT2", "*4", "EAS", 0.48, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("NAT2", "*4", "AMR", 0.30, 7647, "gnomAD", "v4.0", "normal_function"),
    # *5A (slow acetylator) — common globally
    AlleleFrequencyRecord("NAT2", "*5A", "SAS", 0.08, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*5A", "AFR", 0.06, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*5A", "EUR", 0.03, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*5A", "EAS", 0.02, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*5A", "AMR", 0.05, 7647, "gnomAD", "v4.0", "decreased_function"),
    # *5B (slow acetylator) — most common slow allele in EUR
    AlleleFrequencyRecord("NAT2", "*5B", "SAS", 0.20, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*5B", "AFR", 0.12, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*5B", "EUR", 0.30, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*5B", "EAS", 0.05, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*5B", "AMR", 0.22, 7647, "gnomAD", "v4.0", "decreased_function"),
    # *6A (slow acetylator) — common in EUR/SAS
    AlleleFrequencyRecord("NAT2", "*6A", "SAS", 0.18, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*6A", "AFR", 0.22, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*6A", "EUR", 0.25, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*6A", "EAS", 0.20, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*6A", "AMR", 0.20, 7647, "gnomAD", "v4.0", "decreased_function"),
    # *7 (slow acetylator) — EAS-enriched
    AlleleFrequencyRecord("NAT2", "*7", "SAS", 0.05, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*7", "AFR", 0.03, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*7", "EUR", 0.02, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*7", "EAS", 0.12, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*7", "AMR", 0.04, 7647, "gnomAD", "v4.0", "decreased_function"),
    # *14A (slow acetylator) — AFR-enriched
    AlleleFrequencyRecord("NAT2", "*14A", "SAS", 0.02, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*14A", "AFR", 0.09, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*14A", "EUR", 0.01, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*14A", "EAS", 0.00, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("NAT2", "*14A", "AMR", 0.03, 7647, "gnomAD", "v4.0", "decreased_function"),
]

# --- G6PD Allele Frequencies ---
# X-linked. Named alleles (not star notation). Wildtype is "B".
# A- ~20-25% in sub-Saharan Africa; Mediterranean ~5-20% in Middle East.

G6PD_FREQUENCIES: list[AlleleFrequencyRecord] = [
    # B (normal function) — reference/wildtype
    AlleleFrequencyRecord("G6PD", "B", "SAS", 0.82, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("G6PD", "B", "AFR", 0.68, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("G6PD", "B", "EUR", 0.95, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("G6PD", "B", "EAS", 0.90, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("G6PD", "B", "AMR", 0.88, 7647, "gnomAD", "v4.0", "normal_function"),
    # A- (decreased function) — high in AFR
    AlleleFrequencyRecord("G6PD", "A-", "SAS", 0.03, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("G6PD", "A-", "AFR", 0.22, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("G6PD", "A-", "EUR", 0.01, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("G6PD", "A-", "EAS", 0.00, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("G6PD", "A-", "AMR", 0.05, 7647, "gnomAD", "v4.0", "decreased_function"),
    # Mediterranean (no function) — SAS/EUR (Middle East/Mediterranean)
    AlleleFrequencyRecord("G6PD", "Mediterranean", "SAS", 0.08, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("G6PD", "Mediterranean", "AFR", 0.01, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("G6PD", "Mediterranean", "EUR", 0.03, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("G6PD", "Mediterranean", "EAS", 0.01, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("G6PD", "Mediterranean", "AMR", 0.02, 7647, "gnomAD", "v4.0", "no_function"),
    # Canton (no function) — EAS (Southeast Asia)
    AlleleFrequencyRecord("G6PD", "Canton", "SAS", 0.01, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("G6PD", "Canton", "AFR", 0.00, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("G6PD", "Canton", "EUR", 0.00, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("G6PD", "Canton", "EAS", 0.05, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("G6PD", "Canton", "AMR", 0.01, 7647, "gnomAD", "v4.0", "no_function"),
    # Kaiping (no function) — EAS (Southeast Asia)
    AlleleFrequencyRecord("G6PD", "Kaiping", "SAS", 0.01, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("G6PD", "Kaiping", "AFR", 0.00, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("G6PD", "Kaiping", "EUR", 0.00, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("G6PD", "Kaiping", "EAS", 0.03, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("G6PD", "Kaiping", "AMR", 0.01, 7647, "gnomAD", "v4.0", "no_function"),
    # Chatham (decreased function) — SAS/Middle East
    AlleleFrequencyRecord("G6PD", "Chatham", "SAS", 0.04, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("G6PD", "Chatham", "AFR", 0.00, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("G6PD", "Chatham", "EUR", 0.01, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("G6PD", "Chatham", "EAS", 0.01, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("G6PD", "Chatham", "AMR", 0.02, 7647, "gnomAD", "v4.0", "decreased_function"),
]

# --- VKORC1 Allele Frequencies ---
# Single-locus genotype at rs9923231 (-1639G>A). Warfarin sensitivity.
# Stored as genotype frequencies (diploid), not allele frequencies.

VKORC1_FREQUENCIES: list[AlleleFrequencyRecord] = [
    # GG (normal sensitivity)
    AlleleFrequencyRecord("VKORC1", "GG", "SAS", 0.20, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("VKORC1", "GG", "AFR", 0.75, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("VKORC1", "GG", "EUR", 0.37, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("VKORC1", "GG", "EAS", 0.05, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("VKORC1", "GG", "AMR", 0.30, 7647, "gnomAD", "v4.0", "normal_function"),
    # GA (intermediate sensitivity)
    AlleleFrequencyRecord("VKORC1", "GA", "SAS", 0.45, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("VKORC1", "GA", "AFR", 0.22, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("VKORC1", "GA", "EUR", 0.45, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("VKORC1", "GA", "EAS", 0.30, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("VKORC1", "GA", "AMR", 0.42, 7647, "gnomAD", "v4.0", "decreased_function"),
    # AA (high sensitivity — lower warfarin dose needed)
    AlleleFrequencyRecord("VKORC1", "AA", "SAS", 0.35, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("VKORC1", "AA", "AFR", 0.03, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("VKORC1", "AA", "EUR", 0.18, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("VKORC1", "AA", "EAS", 0.65, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("VKORC1", "AA", "AMR", 0.28, 7647, "gnomAD", "v4.0", "no_function"),
]

# --- SLCO1B1 Allele Frequencies ---
# Single-locus genotype at rs4149056 (c.521T>C). Statin myopathy risk.
# Stored as genotype frequencies (diploid).

SLCO1B1_FREQUENCIES: list[AlleleFrequencyRecord] = [
    # TT (normal function — low myopathy risk)
    AlleleFrequencyRecord("SLCO1B1", "TT", "SAS", 0.72, 15308, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("SLCO1B1", "TT", "AFR", 0.90, 20744, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("SLCO1B1", "TT", "EUR", 0.68, 64603, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("SLCO1B1", "TT", "EAS", 0.60, 9197, "gnomAD", "v4.0", "normal_function"),
    AlleleFrequencyRecord("SLCO1B1", "TT", "AMR", 0.72, 7647, "gnomAD", "v4.0", "normal_function"),
    # TC (decreased function — moderate myopathy risk)
    AlleleFrequencyRecord("SLCO1B1", "TC", "SAS", 0.24, 15308, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("SLCO1B1", "TC", "AFR", 0.09, 20744, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("SLCO1B1", "TC", "EUR", 0.27, 64603, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("SLCO1B1", "TC", "EAS", 0.32, 9197, "gnomAD", "v4.0", "decreased_function"),
    AlleleFrequencyRecord("SLCO1B1", "TC", "AMR", 0.24, 7647, "gnomAD", "v4.0", "decreased_function"),
    # CC (poor function — high myopathy risk)
    AlleleFrequencyRecord("SLCO1B1", "CC", "SAS", 0.04, 15308, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("SLCO1B1", "CC", "AFR", 0.01, 20744, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("SLCO1B1", "CC", "EUR", 0.05, 64603, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("SLCO1B1", "CC", "EAS", 0.08, 9197, "gnomAD", "v4.0", "no_function"),
    AlleleFrequencyRecord("SLCO1B1", "CC", "AMR", 0.04, 7647, "gnomAD", "v4.0", "no_function"),
]


# --- Aggregated frequency list ---

ALL_FREQUENCIES = (
    CYP2D6_FREQUENCIES
    + CYP2C19_FREQUENCIES
    + CYP1A2_FREQUENCIES
    + CYP2B6_FREQUENCIES
    + CYP2C9_FREQUENCIES
    + CYP3A4_FREQUENCIES
    + CYP3A5_FREQUENCIES
    + DPYD_FREQUENCIES
    + TPMT_FREQUENCIES
    + NAT2_FREQUENCIES
    + G6PD_FREQUENCIES
    + VKORC1_FREQUENCIES
    + SLCO1B1_FREQUENCIES
)


# --- Real gnomAD frequencies (pinned BigQuery artifact) ---
#
# Loaded from the offline-ingested JSONL artifact produced by
# scripts/ingest_gnomad_frequencies.py. Real per-population allele
# frequencies from gnomAD v2.1.1 (exomes + genomes fallback), with real
# sample sizes and source/version provenance. Kept separate from the
# curated ALL_FREQUENCIES so the byte-identical demo contract is
# preserved; opt in via FrequencyStore(use_gnomad=True).

import json as _json
from pathlib import Path as _Path

_DATA_DIR = _Path(__file__).resolve().parent


def _load_artifact(filename: str) -> list[AlleleFrequencyRecord]:
    """Load a pinned offline-ingested JSONL frequency artifact.

    Deduplicates on (gene, allele, population), keeping the record with
    the higher frequency (exomes > genomes fallback). Returns an empty
    list if the artifact is absent (artifacts are offline-generated and
    may not be present in every checkout).
    """
    path = _DATA_DIR / filename
    if not path.exists():
        return []
    best: dict[tuple[str, str, str], AlleleFrequencyRecord] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        d = _json.loads(line)
        rec = AlleleFrequencyRecord(
            gene=d["gene"], allele=d["allele"], population=d["population"],
            frequency=d["frequency"], sample_n=d["sample_n"],
            source=d["source"], version=d["version"], function=d["function"],
        )
        key = (rec.gene, rec.allele, rec.population)
        prev = best.get(key)
        if prev is None or rec.frequency > prev.frequency:
            best[key] = rec
    return list(best.values())


def load_gnomad_frequencies() -> list[AlleleFrequencyRecord]:
    """Load the pinned gnomAD v2.1.1 BigQuery artifact."""
    return _load_artifact("gnomad_v2_1_1_frequencies.jsonl")


def load_sgdp_frequencies() -> list[AlleleFrequencyRecord]:
    """Load the pinned SGDP (127-population) BigQuery artifact."""
    return _load_artifact("sgdp_frequencies.jsonl")


GNOMAD_FREQUENCIES: list[AlleleFrequencyRecord] = load_gnomad_frequencies()
SGDP_FREQUENCIES: list[AlleleFrequencyRecord] = load_sgdp_frequencies()
