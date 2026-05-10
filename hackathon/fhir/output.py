"""FHIR R4 output adapter — SwarmRuntime report → FHIR resources.

The MCP tools return typed FHIR resources rather than raw JSON so
downstream agents on the Prompt Opinion platform can consume our
Superpower's output through the same FHIR plumbing they use for EHR
data.

We produce three cross-linked resources:

    DetectedIssue        the pharmacogenomic risk (severity, code,
                         implicated medication, evidence)
    ClinicalImpression   the deliberation + recommendation
                         (summary, findings, protocol = CPIC)
    Provenance           the audit chain (target = the above;
                         agents = our swarm; entity = PMIDs)

Each resource is emitted as a ``fhir.resources`` typed model and
round-tripped via ``.model_dump(mode="json", exclude_none=True)`` so
callers receive a stable JSON shape.

Why not just POST to the FHIR server?
-------------------------------------
The platform contract does not require us to persist. Returning the
resources in-band lets the caller decide:

  - A downstream agent may want to chain the DetectedIssue into its
    own prompt *without* storing it (a read-only reasoning step).
  - A write-through caller can `PUT /DetectedIssue/{id}` using the
    same bearer token they passed us — no extra scope needed.
  - A safety-conservative deployment may prefer no writes at all.

This matches the A2A + FHIR pattern described in
https://github.com/prompt-opinion/po-overview.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.runtime.report import UnifiedExecutionReport

    from hackathon.sharp import SharpContext

# -----------------------------------------------------------------------------
# Severity + risk mapping
# -----------------------------------------------------------------------------


# FHIR DetectedIssue.severity is a closed enum: high | moderate | low.
# We map from our phenotype + CPIC strength deterministically.
_STRENGTH_TO_SEVERITY: dict[str, str] = {
    # CPIC recommendation strengths from guidelines/cpic.py
    "strong": "high",
    "moderate": "moderate",
    "recommended": "moderate",
    "optional": "low",
    "no_recommendation": "low",
}

# SNOMED CT concepts for the pharmacogenomic-issue category.
# 182856006 = "Drug interaction with drug"
# We use a closer match where available.
_DETECTED_ISSUE_CODE = {
    "system": "http://snomed.info/sct",
    "code": "405298005",
    "display": "Drug-gene interaction",
}

# LOINC for the ClinicalImpression code — "Clinical note (genomic)".
_CLINICAL_IMPRESSION_CODE = {
    "system": "http://loinc.org",
    "code": "81247-9",
    "display": "Master HL7 genetic variant reporting panel",
}

# Our MCP server's canonical Prompt Opinion marketplace id. Used as
# the provenance agent identifier so callers can reverse-link the
# result back to the Superpower that produced it.
ANUKRITI_SUPERPOWER_ID = (
    "https://marketplace.promptopinion.ai/superpower/anukriti-pgx"
)


# -----------------------------------------------------------------------------
# DetectedIssue
# -----------------------------------------------------------------------------


def to_detected_issue(
    report: UnifiedExecutionReport,
    *,
    patient_id: str | None = None,
    issue_id: str | None = None,
) -> dict[str, Any]:
    """Build a FHIR R4 ``DetectedIssue`` from a UnifiedExecutionReport.

    The issue's severity reflects the recommendation strength; the
    evidence block carries every PMID/CPIC guideline id the swarm
    cited; and the ``mitigation`` array records any alternative drug
    the narrative suggested.

    Returns a JSON-serialisable dict (the output of ``.model_dump``)
    rather than the typed model so callers don't need fhir.resources
    installed transitively.
    """

    from fhir.resources.detectedissue import DetectedIssue

    rec = report.final_recommendation or {}
    severity = _map_severity(rec.get("strength"))
    evidence = _build_evidence_array(rec.get("evidence_refs") or [])
    issue_id = issue_id or f"anukriti-di-{uuid.uuid4().hex[:12]}"

    issue = DetectedIssue.model_validate(
        {
            "resourceType": "DetectedIssue",
            "id": issue_id,
            "status": "final",
            # ``category`` in R4 is a list of CodeableConcept. One entry
            # is plenty — this is how our DetectedIssue is typed.
            "category": [
                {
                    "coding": [_DETECTED_ISSUE_CODE],
                    "text": f"{report.gene} drug-gene interaction for {report.drug}",
                }
            ],
            "severity": severity,
            "identifiedDateTime": datetime.now(UTC).isoformat(),
            # ``author`` is a single Reference in R4.
            "author": {"display": "Anukriti PGx Swarm"},
            "implicated": [{"display": report.drug}],
            "detail": rec.get("text") or _fallback_detail(report),
            "evidence": evidence,
            "mitigation": _build_mitigation(rec),
            **_maybe_subject(patient_id),
        }
    )
    return issue.model_dump(mode="json", exclude_none=True)


# -----------------------------------------------------------------------------
# ClinicalImpression
# -----------------------------------------------------------------------------


def to_clinical_impression(
    report: UnifiedExecutionReport,
    *,
    patient_id: str | None = None,
    impression_id: str | None = None,
    detected_issue_id: str | None = None,
) -> dict[str, Any]:
    """Build a FHIR R4 ``ClinicalImpression`` from a UnifiedExecutionReport.

    The impression's ``summary`` carries the narrative text; the
    ``finding`` array records every activated specialist + its
    conclusion; the ``protocol`` field points at the CPIC guideline
    id(s) we cited.
    """

    from fhir.resources.clinicalimpression import ClinicalImpression

    rec = report.final_recommendation or {}
    impression_id = impression_id or f"anukriti-ci-{uuid.uuid4().hex[:12]}"

    findings = _build_findings(report)
    protocols = _build_protocols(rec.get("evidence_refs") or [])

    status = "completed" if rec.get("allows_synthesis", True) else "in-progress"

    impression_payload: dict[str, Any] = {
        "resourceType": "ClinicalImpression",
        "id": impression_id,
        "status": status,
        "description": (
            f"Pharmacogenomic analysis for {report.gene} {report.genotype} "
            f"in a {report.population} patient on {report.drug}."
        ),
        "effectiveDateTime": datetime.now(UTC).isoformat(),
        "date": report.generated_at.isoformat() if report.generated_at else None,
        "summary": rec.get("text") or _fallback_detail(report),
        "finding": findings,
        "protocol": protocols,
    }

    if detected_issue_id:
        impression_payload["problem"] = [
            {"reference": f"DetectedIssue/{detected_issue_id}"}
        ]

    if patient_id:
        impression_payload["subject"] = {"reference": f"Patient/{patient_id}"}
    else:
        # Required field in R4; use a placeholder to keep the resource
        # schema-valid even when the call was population-level.
        impression_payload["subject"] = {"display": "No patient in context"}

    impression = ClinicalImpression.model_validate(impression_payload)
    return impression.model_dump(mode="json", exclude_none=True)


# -----------------------------------------------------------------------------
# Provenance
# -----------------------------------------------------------------------------


def to_provenance(
    report: UnifiedExecutionReport,
    *,
    sharp_context: SharpContext | None,
    target_refs: list[str],
    provenance_id: str | None = None,
) -> dict[str, Any]:
    """Build a FHIR R4 ``Provenance`` resource for ``target_refs``.

    ``target_refs`` is the list of ``ResourceType/id`` strings the
    caller wants stamped with this Provenance (typically the
    DetectedIssue + ClinicalImpression we just emitted).

    The ``agent`` array records:
      1. Our Superpower (as an MCP tool source).
      2. The Prompt Opinion session (from SHARP context, when
         present) so the chain reaches the original EHR user.

    The ``entity`` array carries every cited PMID / CPIC guideline as
    a ``supporting`` role so a downstream auditor can navigate from
    recommendation → evidence.
    """

    from fhir.resources.provenance import Provenance

    rec = report.final_recommendation or {}
    provenance_id = provenance_id or f"anukriti-prov-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(UTC).isoformat()

    agents = [
        {
            "type": {
                "coding": [
                    {
                        "system": (
                            "http://terminology.hl7.org/CodeSystem/"
                            "provenance-participant-type"
                        ),
                        "code": "assembler",
                        "display": "Assembler",
                    }
                ]
            },
            "who": {
                "identifier": {
                    "system": "https://promptopinion.ai/ns/superpower",
                    "value": "anukriti-pgx",
                },
                "display": "Anukriti PGx Swarm",
            },
            "onBehalfOf": {
                "identifier": {
                    "system": "https://promptopinion.ai/ns/superpower",
                    "value": ANUKRITI_SUPERPOWER_ID,
                }
            },
        }
    ]

    if sharp_context is not None:
        agents.append(
            {
                "type": {
                    "coding": [
                        {
                            "system": (
                                "http://terminology.hl7.org/CodeSystem/"
                                "provenance-participant-type"
                            ),
                            "code": "custodian",
                            "display": "Custodian",
                        }
                    ]
                },
                "who": {
                    "identifier": {
                        "system": "https://promptopinion.ai/ns/sharp-session",
                        "value": sharp_context.provenance_agent_id(),
                    },
                    "display": "Prompt Opinion SHARP session",
                },
            }
        )

    entities = _build_provenance_entities(rec.get("evidence_refs") or [])

    payload: dict[str, Any] = {
        "resourceType": "Provenance",
        "id": provenance_id,
        "target": [{"reference": ref} for ref in target_refs],
        "recorded": now_iso,
        "occurredDateTime": now_iso,
        "activity": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/v3-DataOperation",
                    "code": "CREATE",
                    "display": "create",
                }
            ],
            "text": "Pharmacogenomic analysis via Anukriti PGx Superpower",
        },
        "agent": agents,
    }
    if entities:
        payload["entity"] = entities

    return Provenance.model_validate(payload).model_dump(mode="json", exclude_none=True)


# -----------------------------------------------------------------------------
# One-call bundle
# -----------------------------------------------------------------------------


def build_response_bundle(
    report: UnifiedExecutionReport,
    *,
    sharp_context: SharpContext | None,
    patient_id: str | None = None,
) -> dict[str, Any]:
    """Build a typed dict with all three FHIR resources cross-linked.

    Returns a shape MCP tools can pass straight through to their
    response:

        {
          "detectedIssue":       {... FHIR DetectedIssue ...},
          "clinicalImpression":  {... FHIR ClinicalImpression ...},
          "provenance":          {... FHIR Provenance ...},
          "correlationId":       "unified_abc123...",
          "recommendation":      "Use prasugrel or ticagrelor instead..."
        }
    """

    # Prefer the patient id from the explicit arg, fall back to the
    # SHARP context's patient if present.
    effective_patient = patient_id or (
        sharp_context.patient_id if sharp_context is not None else None
    )

    di = to_detected_issue(report, patient_id=effective_patient)
    ci = to_clinical_impression(
        report,
        patient_id=effective_patient,
        detected_issue_id=di.get("id"),
    )
    prov = to_provenance(
        report,
        sharp_context=sharp_context,
        target_refs=[
            f"DetectedIssue/{di.get('id')}",
            f"ClinicalImpression/{ci.get('id')}",
        ],
    )

    rec = report.final_recommendation or {}

    return {
        "detectedIssue": di,
        "clinicalImpression": ci,
        "provenance": prov,
        "correlationId": report.correlation_id,
        "recommendation": rec.get("text", ""),
        "strength": rec.get("strength", ""),
        "allowsSynthesis": rec.get("allows_synthesis", True),
        "blockingReason": rec.get("blocking_reason", ""),
    }


# -----------------------------------------------------------------------------
# Private builders
# -----------------------------------------------------------------------------


def _map_severity(strength: str | None) -> str:
    """Map CPIC recommendation strength → FHIR DetectedIssue.severity."""
    if not strength:
        return "moderate"
    return _STRENGTH_TO_SEVERITY.get(strength.lower(), "moderate")


def _build_evidence_array(refs: list[str]) -> list[dict[str, Any]]:
    """Build ``DetectedIssue.evidence`` entries from raw PMIDs / CPIC ids."""

    evidence: list[dict[str, Any]] = []
    for ref in refs:
        if not ref:
            continue
        pure = str(ref).strip()
        system, value = _classify_evidence_ref(pure)
        codings = [{"system": system, "code": value, "display": pure}] if system else []
        evidence.append(
            {
                "code": [
                    {
                        "coding": codings or None,
                        "text": pure,
                    }
                ],
            }
        )
    return evidence


def _classify_evidence_ref(ref: str) -> tuple[str, str]:
    """Best-effort system + code for an evidence reference string."""
    lower = ref.lower()
    if lower.startswith("pmid:"):
        return "https://pubmed.ncbi.nlm.nih.gov", ref.split(":", 1)[1].strip()
    if lower.startswith("cpic:"):
        return "https://cpicpgx.org/guidelines", ref
    if lower.startswith("pa"):  # PharmGKB accession (e.g. PA166169660)
        return "https://www.pharmgkb.org", ref
    return "", ref


def _build_mitigation(rec: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract alternative-drug mitigations from recommendation text."""

    text = str(rec.get("text") or "")
    if not text:
        return []

    # Very lightweight extraction — we look for "Recommended: X" or
    # "Use X instead" patterns. The swarm's narrative engine emits
    # this pattern consistently.
    import re

    mitigations: list[dict[str, Any]] = []
    pattern = re.compile(
        r"(?:recommended|use)\s*:?\s*([a-z][a-z\- ]+?)(?:\s+instead|\s+or\s+|\.|,|$)",
        re.IGNORECASE,
    )
    seen: set[str] = set()
    for match in pattern.finditer(text):
        candidate = match.group(1).strip().lower()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        mitigations.append(
            {
                "action": {"text": f"Consider alternative: {candidate}"},
                "author": {"display": "Anukriti PGx Swarm"},
            }
        )
    return mitigations


def _build_findings(report: UnifiedExecutionReport) -> list[dict[str, Any]]:
    """Assemble ClinicalImpression.finding from activated agents + rules.

    R5 shape: ``finding[].item.concept`` or ``finding[].item.reference``.
    We use ``concept`` with a ``text`` so the caller can render it
    without dereferencing a CodeableReference.
    """

    findings: list[dict[str, Any]] = []

    for agent in report.activated_agents:
        findings.append(
            {
                "item": {"concept": {"text": f"Specialist activated: {agent}"}},
            }
        )

    # Deterministic rule ids that fired — the PGx analogue of CDSR.
    rules = [r for r in report.deterministic_rules if r]
    if rules:
        findings.append(
            {
                "item": {
                    "concept": {
                        "text": "Deterministic rules triggered: "
                        + ", ".join(rules),
                    }
                },
            }
        )

    # Population-equity footnote — baked in because this is the whole
    # point of the project.
    findings.append(
        {
            "item": {
                "concept": {
                    "text": (
                        f"Population context: {report.population}. "
                        "Allele frequency and Hardy-Weinberg prevalence "
                        "evaluated on population-weighted KG paths."
                    )
                }
            },
        }
    )

    return findings


def _build_protocols(refs: list[str]) -> list[str]:
    """ClinicalImpression.protocol = list of CPIC / PharmGKB canonical URIs."""

    protocols: list[str] = []
    for ref in refs:
        if not ref:
            continue
        pure = str(ref).strip()
        lower = pure.lower()
        if lower.startswith("cpic:"):
            protocols.append(f"https://cpicpgx.org/guidelines/#{pure}")
        elif lower.startswith("pa"):
            protocols.append(f"https://www.pharmgkb.org/pathway/{pure}")
    return protocols


def _build_provenance_entities(refs: list[str]) -> list[dict[str, Any]]:
    """Provenance.entity array — one per cited PMID / CPIC / PharmGKB id."""

    entities: list[dict[str, Any]] = []
    for ref in refs:
        if not ref:
            continue
        pure = str(ref).strip()
        lower = pure.lower()

        if lower.startswith("pmid:"):
            pmid = pure.split(":", 1)[1].strip()
            entities.append(
                {
                    "role": "source",
                    "what": {
                        "identifier": {
                            "system": "https://pubmed.ncbi.nlm.nih.gov/",
                            "value": pmid,
                        },
                        "display": f"PubMed {pmid}",
                    },
                }
            )
        elif lower.startswith("cpic:"):
            entities.append(
                {
                    "role": "source",
                    "what": {
                        "identifier": {
                            "system": "https://cpicpgx.org/guidelines",
                            "value": pure,
                        },
                        "display": pure,
                    },
                }
            )
        elif lower.startswith("pa"):
            entities.append(
                {
                    "role": "source",
                    "what": {
                        "identifier": {
                            "system": "https://www.pharmgkb.org",
                            "value": pure,
                        },
                        "display": f"PharmGKB {pure}",
                    },
                }
            )
    return entities


def _fallback_detail(report: UnifiedExecutionReport) -> str:
    rec = report.final_recommendation or {}
    if rec.get("blocking_reason"):
        return f"Analysis blocked: {rec['blocking_reason']}"
    return (
        f"Pharmacogenomic analysis for {report.gene} {report.genotype} "
        f"in a {report.population} patient on {report.drug}. "
        f"{len(report.activated_agents)} specialists activated, "
        f"{len(report.deterministic_rules)} deterministic rules fired."
    )


def _maybe_subject(patient_id: str | None) -> dict[str, Any]:
    """DetectedIssue.subject optional in R4 but highly desired when present."""
    if not patient_id:
        return {}
    return {"subject": {"reference": f"Patient/{patient_id}"}}
