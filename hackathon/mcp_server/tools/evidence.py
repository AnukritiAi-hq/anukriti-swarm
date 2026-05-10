"""``pgx_retrieve_evidence`` — cited CPIC/PubMed passages for a query.

Wraps the existing ``QueryPlanner + EvidenceRetriever + EvidenceSynthesizer``
pipeline. Returns the same citation set the SwarmRuntime would ground
its narrative on — so a downstream agent can do its own synthesis
while still getting our evidence fabric.

Does NOT run the deterministic rule engine — call
``pgx_analyze_patient`` for that.
"""

from __future__ import annotations

from typing import Any

from fastmcp.tools import tool

from hackathon.mcp_server.tools._common import make_error, read_sharp
from retrieval.evidence.retriever import EvidenceRetriever
from retrieval.evidence.synthesizer import EvidenceSynthesizer
from retrieval.planner.query_planner import QueryPlanner


# Reusable singletons — these are stateless.
_PLANNER = QueryPlanner()
_RETRIEVER = EvidenceRetriever()
_SYNTHESIZER = EvidenceSynthesizer()


@tool()
def pgx_retrieve_evidence(
    gene: str,
    drug: str,
    population: str,
    max_results: int = 8,
) -> dict[str, Any]:
    """Return cited CPIC/PubMed/PharmGKB passages for a PGx query.

    Inputs:
        gene         e.g. "CYP2C19"
        drug         e.g. "clopidogrel"
        population   3-letter SuperPopulation code
        max_results  hard cap on returned claims (defaults to 8)

    Returns:
        {
          "ok": True,
          "claims": [
            {
              "claim":      "...",          # passage text (truncated)
              "citations":  ["PMID:...", "CPIC:..."],
              "grounded":   true,
              "confidence": 0.95
            }, ...
          ],
          "citations":      ["PMID:34032273", ...],  # dedup'd list
          "groundingScore": 0.92,
          "totalRetrieved": 12,
          "strategy":       "population_aware+dense"
        }
    """

    _ = read_sharp()

    gene_key = str(gene).strip().upper()
    drug_key = str(drug).strip().lower()
    pop_key = str(population).strip().upper()

    if not gene_key or not drug_key or not pop_key:
        return make_error(
            "missing_argument",
            "gene, drug, and population are all required",
            details={"gene": gene, "drug": drug, "population": population},
        )

    plan = _PLANNER.plan(
        f"{gene_key} {drug_key} {pop_key} pharmacogenomics",
        gene=gene_key,
        drug=drug_key,
        population=pop_key,
    )

    try:
        result = _RETRIEVER.execute_plan(plan)
        synthesis = _SYNTHESIZER.synthesize(result)
    except Exception as exc:  # pragma: no cover — defensive
        return make_error(
            "retrieval_failed",
            f"evidence retrieval failed: {exc!r}",
            details={"gene": gene_key, "drug": drug_key, "population": pop_key},
        )

    # Truncate claim text so responses stay compact.
    claims: list[dict[str, Any]] = []
    for c in synthesis.claims[: max(1, int(max_results))]:
        claims.append(
            {
                "claim": c.claim[:500],
                "citations": list(c.citations),
                "grounded": bool(c.grounded),
                "confidence": float(c.confidence),
            }
        )

    return {
        "ok": True,
        "claims": claims,
        "citations": [c.citation_id for c in result.citations],
        "groundingScore": float(synthesis.grounding_score),
        "totalRetrieved": int(result.total_retrieved),
        "strategy": getattr(result, "strategy", "default"),
    }
