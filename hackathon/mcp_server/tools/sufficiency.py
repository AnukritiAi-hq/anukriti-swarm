"""``pgx_sufficiency_check`` — can we safely answer this right now?

Wraps the existing ``ContextSufficiencyAgent`` (session #6's evidence
governance layer). Lets a calling agent ask, *before* expensive
synthesis, whether our evidence fabric can support a safe answer for
a given tuple.

This is the most subtle of the five tools and arguably the biggest
differentiator — most healthcare AI demos don't abstain. We cite a
specific rule id (R1..R12) on every refusal.
"""

from __future__ import annotations

from typing import Any

from fastmcp.tools import tool

from core.runtime import SwarmRuntime, UnifiedExecutionContext
from hackathon.fhir import UnsupportedFHIRInput
from hackathon.mcp_server.tools._common import (
    build_patient_context,
    make_error,
    read_sharp,
)


# Sufficiency runs inside the SwarmRuntime as stage 3.5. We use the
# shared runtime here too so the KG/indexer work is reused across
# calls.
_RUNTIME = SwarmRuntime()


@tool()
def pgx_sufficiency_check(
    drug: str,
    gene: str,
    population: str | None = None,
    genotype: str | None = None,
    patient: dict[str, Any] | None = None,
    observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return whether our evidence fabric can support a safe answer.

    Inputs match ``pgx_analyze_patient`` minus the free-form
    ``question`` (which is irrelevant to sufficiency).

    Returns:
        {
          "ok": True,
          "allowsSynthesis": true,
          "decision": "sufficient" | "insufficient_coverage" | ...,
          "blockingReason": "",
          "ruleIds": ["R1", "V3"],            # which rules fired
          "coverage": {
            "facets": {"phenotype": "supported", "population": "supported", ...},
            "coverageScore": 0.92
          },
          "uncertainty": {"tier": "low", "score": 0.08, "action": "proceed"},
          "biasFindings": []
        }
    """

    _ = read_sharp()

    try:
        pgx_ctx = build_patient_context(
            drug=drug,
            gene=gene,
            population=population,
            genotype=genotype,
            patient=patient,
            observations=observations,
        )
    except UnsupportedFHIRInput as exc:
        return make_error("missing_prerequisite", str(exc))

    unified_ctx = UnifiedExecutionContext.new(**pgx_ctx.to_swarm_kwargs())
    report = _RUNTIME.run(unified_ctx)

    rec = report.final_recommendation or {}
    checkpoint = report.evidence_sufficiency or {}

    coverage = checkpoint.get("coverage") or {}
    uncertainty = report.uncertainty_analysis or {}

    return {
        "ok": True,
        "allowsSynthesis": rec.get("allows_synthesis", True),
        "decision": checkpoint.get("decision", ""),
        "blockingReason": rec.get("blocking_reason", ""),
        "ruleIds": list(report.deterministic_rules),
        "coverage": {
            "facets": coverage.get("facets", {}),
            "coverageScore": coverage.get("coverage_score"),
        },
        "uncertainty": {
            "tier": uncertainty.get("tier"),
            "score": uncertainty.get("score"),
            "action": uncertainty.get("action"),
        },
        "biasFindings": uncertainty.get("bias_findings", []),
    }
