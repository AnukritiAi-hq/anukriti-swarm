"""PharmFreq-compatible allele frequency data.

Mock data based on real pharmacogenomic allele frequencies from:
- PharmFreq (https://www.pharmfreq.org/)
- gnomAD v4.0
- 1000 Genomes Phase 3

Frequencies are realistic approximations for demonstration.
Schema follows PharmFreq conventions: gene, allele, population, frequency, sample_n.

Genes covered:
- CYP2D6: codeine, tamoxifen, antidepressants
- CYP2C19: clopidogrel, PPIs, antidepressants
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AlleleFrequencyRecord:
    """A single allele frequency observation in a population.

    PharmFreq-compatible schema with provenance fields.
    """

    gene: str
    allele: str           # Star allele (e.g., "*4")
    population: str       # Super-population code (SAS, AFR, EUR, EAS, AMR)
    frequency: float      # Allele frequency (0.0 - 1.0)
    sample_n: int         # Number of samples in reference
    source: str           # Data source
    version: str          # Source version
    function: str         # "no_function", "decreased_function", "normal_function", "increased_function"


# --- CYP2D6 Allele Frequencies ---
# Based on PharmFreq/gnomAD data

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

ALL_FREQUENCIES = CYP2D6_FREQUENCIES + CYP2C19_FREQUENCIES
