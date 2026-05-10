"""Shared helpers for MCP tool implementations.

Keeping the error-envelope builders + SHARP-aware context builders
in one place so each tool stays focused on its domain.
"""

from __future__ import annotations

from typing import Any

from hackathon.fhir import (
    PatientGenomicContext,
    UnsupportedFHIRInput,
    build_context_from_args,
    build_context_from_fhir,
)
from hackathon.sharp import SharpContext, SharpContextMissing, get_sharp_context


def make_error(
    kind: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a structured error envelope returned to the MCP caller.

    Shape:
        {
          "ok": False,
          "error": { "kind": "...", "message": "...", "details": {...} }
        }

    Prompt Opinion's platform surfaces the ``message`` to the user
    and logs the full envelope.
    """
    body: dict[str, Any] = {"kind": kind, "message": message}
    if details:
        body["details"] = details
    return {"ok": False, "error": body}


def read_sharp() -> SharpContext | None:
    """Return the current SHARP context, or None if not present.

    Tools call this before attempting any FHIR read. When None, the
    tool must either accept explicit arguments or abstain.
    """
    return get_sharp_context()


def build_patient_context(
    *,
    drug: str,
    gene: str,
    population: str | None,
    genotype: str | None,
    # FHIR payloads the caller may pass in-band:
    patient: dict[str, Any] | None = None,
    observations: list[dict[str, Any]] | None = None,
    molecular_sequence: dict[str, Any] | None = None,
    question: str = "",
) -> PatientGenomicContext:
    """Pick between explicit-args and FHIR-driven context building.

    Priority:
      1. If population + genotype are both explicit, build from args.
      2. If patient is supplied (even without observations), try FHIR.
      3. Otherwise raise ``UnsupportedFHIRInput``.
    """

    if population and genotype:
        return build_context_from_args(
            drug=drug,
            gene=gene,
            population=population,
            genotype=genotype,
            question=question,
        )

    if patient is not None or observations:
        return build_context_from_fhir(
            drug=drug,
            gene=gene,
            patient=patient,
            observations=observations,
            molecular_sequence=molecular_sequence,
            population_override=population,
            genotype_override=genotype,
            question=question,
        )

    raise UnsupportedFHIRInput(
        "Need either (population + genotype) explicitly, or a FHIR Patient "
        "with us-core-race + PGx Observations"
    )


__all__ = [
    "SharpContextMissing",
    "UnsupportedFHIRInput",
    "build_patient_context",
    "make_error",
    "read_sharp",
]
