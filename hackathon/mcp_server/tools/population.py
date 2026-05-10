"""``pgx_population_risk`` — allele frequency + prevalence lookup.

A population-level tool. No patient needed, no FHIR context required
(though SHARP context is still accepted for provenance linkage).

Returns structured data directly from the existing population agents
(``SASPopulationAgent`` / ``AFRPopulationAgent`` / ``EURPopulationAgent``)
without running the full SwarmRuntime.
"""

from __future__ import annotations

from typing import Any

from fastmcp.tools import tool

from hackathon.mcp_server.tools._common import make_error, read_sharp
from population.agents import (
    AFRPopulationAgent,
    EURPopulationAgent,
    SASPopulationAgent,
)


_POPULATION_AGENTS = {
    "AFR": AFRPopulationAgent(),
    "EUR": EURPopulationAgent(),
    "SAS": SASPopulationAgent(),
}


@tool()
def pgx_population_risk(
    gene: str,
    allele: str,
    population: str,
) -> dict[str, Any]:
    """Return allele-frequency + prevalence risk for a population.

    Inputs:
        gene         e.g. "CYP2C19"
        allele       e.g. "*2" or "*15:02"
        population   3-letter SuperPopulation code (AFR/EUR/SAS)
                     (AMR and EAS agents are not yet in the catalogue)

    Returns:
        {
          "ok": True,
          "population": "SAS",
          "gene": "CYP2C19",
          "allele": "*2",
          "frequency": 0.36,
          "rarity": "common",
          "sampleN": 15000,
          "source": "gnomAD v4.0",
          "clinicalNote": "36% of SAS individuals carry CYP2C19*2...",
          "confidence": 0.95,
          "prevalenceByPhenotype": [
            {"phenotype": "PM", "prevalence": 0.13},
            {"phenotype": "IM", "prevalence": 0.46},
            ...
          ],
          "warnings": []
        }
    """

    # Read SHARP for provenance side-effects but don't require it.
    _ = read_sharp()

    pop_key = str(population).strip().upper()
    if pop_key not in _POPULATION_AGENTS:
        return make_error(
            "unsupported_population",
            f"Population {pop_key!r} is not in the Anukriti catalogue. "
            f"Supported: {sorted(_POPULATION_AGENTS.keys())}",
            details={
                "supported": sorted(_POPULATION_AGENTS.keys()),
                "requested": pop_key,
            },
        )

    gene_key = str(gene).strip().upper()
    allele_key = str(allele).strip()
    if not gene_key or not allele_key:
        return make_error(
            "missing_argument",
            "both 'gene' and 'allele' are required",
            details={"gene": gene_key, "allele": allele_key},
        )

    agent = _POPULATION_AGENTS[pop_key]
    result = agent.reason(gene_key, allele_key)

    return {
        "ok": True,
        "population": result.population,
        "gene": gene_key,
        "allele": allele_key,
        "frequency": result.frequency.frequency,
        "rarity": result.risk_context.rarity_class,
        "sampleN": result.frequency.sample_n,
        "source": f"{result.frequency.source} {result.frequency.version}".strip(),
        "clinicalNote": result.risk_context.clinical_note,
        "confidence": result.confidence,
        "prevalenceByPhenotype": [
            {"phenotype": p.phenotype, "prevalence": p.prevalence}
            for p in result.prevalence_estimates
        ],
        "warnings": [
            {
                "reason": w.reason,
                "severity": w.severity,
                "recommendation": w.recommendation,
            }
            for w in (result.warnings or [])
        ],
    }
