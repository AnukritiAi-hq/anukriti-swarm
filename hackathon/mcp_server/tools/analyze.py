"""``pgx_analyze_patient`` — end-to-end pharmacogenomic analysis.

The flagship tool. Given a drug + gene + (patient context), returns
the full swarm recommendation as FHIR R5 resources.

Inputs
------
drug      str      e.g. "clopidogrel"
gene      str      e.g. "CYP2C19"
population          str or None — explicit SuperPopulation 3-letter
                   code (AFR/AMR/EAS/EUR/SAS). When None the tool
                   tries to infer from the FHIR Patient resource
                   passed inline OR from the SHARP-context patient.
genotype            str or None — diplotype (e.g. "*2/*2"). When
                   None the tool tries to extract from the passed
                   FHIR Observations OR from the SHARP patient's
                   chart.
patient            dict | None — FHIR Patient resource (optional).
observations       list[dict] | None — FHIR Observations (optional).
question           free-form natural-language question for narrative
                   synthesis.

Returns
-------
On success:
    {
      "ok": True,
      "detectedIssue":      <FHIR R5 DetectedIssue>,
      "clinicalImpression": <FHIR R5 ClinicalImpression>,
      "provenance":         <FHIR R5 Provenance>,
      "correlationId":      "unified_abc123",
      "recommendation":     "Use prasugrel or ticagrelor instead...",
      "strength":           "recommended",
      "allowsSynthesis":    true,
      "activatedAgents":    ["orchestrator", ...],
      "durationMs":         25.4
    }

On abstention (not enough evidence):
    {"ok": True, "allowsSynthesis": False, "blockingReason": "...",
     "clinicalImpression": <with status="in-progress">, ...}

On error:
    {"ok": False, "error": {"kind": "...", "message": "..."}}
"""

from __future__ import annotations

from typing import Any

from fastmcp.tools import tool

from core.runtime import SwarmRuntime, UnifiedExecutionContext
from hackathon.fhir import build_response_bundle
from hackathon.mcp_server.tools._common import (
    UnsupportedFHIRInput,
    build_patient_context,
    make_error,
    read_sharp,
)


# Shared SwarmRuntime — components (KG, retrievers, checkpoint) are
# built lazily on first run and reused across every call. Instantiating
# one per tool call would rebuild ~40ms of graph context every time.
_RUNTIME = SwarmRuntime()


@tool()
def pgx_analyze_patient(
    drug: str,
    gene: str,
    population: str | None = None,
    genotype: str | None = None,
    patient: dict[str, Any] | None = None,
    observations: list[dict[str, Any]] | None = None,
    question: str = "",
) -> dict[str, Any]:
    """End-to-end pharmacogenomic analysis for a drug-gene-patient tuple.

    Runs the full 5-stage SwarmRuntime (orchestration → retrieval →
    graph reasoning → sufficiency → synthesis) and returns the result
    as FHIR R5 resources. Every claim cites its CPIC / PubMed source;
    deterministic rules fire before any LLM narrative is generated.

    Pass ``population`` + ``genotype`` explicitly for demos with no
    FHIR server, or pass ``patient`` + ``observations`` to let the
    tool infer them from FHIR.
    """

    sharp = read_sharp()

    try:
        pgx_ctx = build_patient_context(
            drug=drug,
            gene=gene,
            population=population,
            genotype=genotype,
            patient=patient,
            observations=observations,
            question=question,
        )
    except UnsupportedFHIRInput as exc:
        return make_error(
            "missing_prerequisite",
            str(exc),
            details={
                "drug": drug,
                "gene": gene,
                "hint": (
                    "Provide 'population' (AFR/AMR/EAS/EUR/SAS) + 'genotype' "
                    "(e.g. '*2/*2') explicitly, OR a FHIR Patient with the "
                    "us-core-race extension plus PGx Observations."
                ),
            },
        )

    try:
        unified_ctx = UnifiedExecutionContext.new(**pgx_ctx.to_swarm_kwargs())
        report = _RUNTIME.run(unified_ctx)
    except Exception as exc:  # pragma: no cover — defensive
        return make_error(
            "runtime_error",
            f"SwarmRuntime failed: {exc!r}",
            details={"drug": drug, "gene": gene},
        )

    # Use SHARP-context patient id when available so the DetectedIssue
    # references the correct Patient/{id} in the caller's FHIR server.
    patient_id = pgx_ctx.patient_id or (
        sharp.patient_id if sharp is not None else None
    )

    bundle = build_response_bundle(
        report,
        sharp_context=sharp,
        patient_id=patient_id,
    )
    bundle["ok"] = True
    bundle["activatedAgents"] = list(report.activated_agents)
    bundle["deterministicRules"] = list(report.deterministic_rules)
    bundle["durationMs"] = report.total_duration_ms
    return bundle
