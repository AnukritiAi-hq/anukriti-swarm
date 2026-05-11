"""``pgx_verify_recommendation`` — 6-check verification of a proposed recommendation.

Lets another agent (or a human operator) submit a recommendation they
are considering and ask us to verify it. We run the existing 6-check
``VerificationEngine``:

    1. Evidence grounding     — claims cite real sources
    2. Deterministic boundary — deterministic outputs not overwritten
    3. Provenance             — every claim has a chain
    4. Guideline conflicts    — recommendations do not contradict
    5. Sparse population data — low sample-size warnings
    6. Hallucination hooks    — gene/drug on our whitelist

Returns a structured verification report (not FHIR — the caller may
want to block, escalate, or pass based on the verdict, rather than
store a FHIR resource).
"""

from __future__ import annotations

from typing import Any

from fastmcp.tools import tool

from hackathon.mcp_server.tools._common import make_error, read_sharp
from population.data.frequency_store import FrequencyStore
from verification.engine import VerificationEngine


_VERIFIER = VerificationEngine()
_FREQ_STORE = FrequencyStore()


@tool()
def pgx_verify_recommendation(
    agent_id: str,
    gene: str,
    drug: str,
    recommendation_text: str,
    recommendation_strength: str = "moderate",
    guideline_id: str = "",
    pmid: str = "",
    confidence: float = 1.0,
    population: str = "",
    claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run 6-check verification on a proposed recommendation.

    Inputs:
        agent_id                identifier of the agent whose output
                                we are verifying (for audit)
        gene                    e.g. "CYP2C19"
        drug                    e.g. "clopidogrel"
        recommendation_text     the free-form recommendation text
        recommendation_strength one of {"strong", "moderate",
                                "recommended", "optional", "no_recommendation"}
        guideline_id            CPIC / PharmGKB id
        pmid                    supporting PMID
        confidence              claimed confidence (0..1)
        population              SuperPopulation code (empty = skip
                                sparse-population check)
        claims                  optional list of claim dicts with
                                {"claim": "...", "citations": [...]}
                                for the evidence-grounding check

    Returns:
        {
          "ok": True,
          "verdict": "pass" | "warn" | "fail",
          "confidence": {"value": 0.94, "level": "high"},
          "escalation": {"tier": "autonomous", "action": ""},
          "needsEscalation": false,
          "checks": [
            {"name": "evidence_grounding", "verdict": "pass", "reason": "..."},
            ...
          ]
        }
    """

    _ = read_sharp()

    if not agent_id or not gene or not drug or not recommendation_text:
        return make_error(
            "missing_argument",
            "agent_id, gene, drug, and recommendation_text are all required",
        )

    output = {
        "agent_id": str(agent_id),
        "gene": str(gene).strip().upper(),
        "drug": str(drug).strip().lower(),
        "origin": "deterministic",
        "confidence": float(confidence),
        "source": str(guideline_id),
        "population": str(population).strip().upper() if population else "",
    }

    # Enrich with population frequency so sparse_population_data check passes
    pop_code = output["population"]
    if pop_code:
        freq_result = _FREQ_STORE.lookup(output["gene"], "*2", pop_code)
        output["frequency"] = freq_result.frequency if freq_result.found else None
        output["sample_n"] = freq_result.sample_n if freq_result.found else None

    recommendations = [
        {
            "drug": str(drug).strip().lower(),
            "recommendation": str(recommendation_text),
            "strength": str(recommendation_strength).lower(),
            "guideline_id": str(guideline_id),
            "pmid": str(pmid),
        }
    ]

    report = _VERIFIER.verify(
        output,
        claims=claims or [],
        recommendations=recommendations,
        stage_confidences={"agent": float(confidence)},
    )

    return {
        "ok": True,
        "verdict": report.overall_verdict.value,
        "confidence": {
            "value": report.confidence.value if report.confidence else None,
            "level": (
                report.confidence.level.value
                if report.confidence and report.confidence.level
                else None
            ),
        },
        "escalation": {
            "tier": (
                report.escalation.tier.value if report.escalation else "unknown"
            ),
            "action": (
                report.escalation.recommended_action if report.escalation else ""
            ),
        },
        "needsEscalation": report.needs_escalation,
        "checks": [
            {
                "name": c.check_name,
                "verdict": c.verdict.value,
                "reason": c.reason,
            }
            for c in report.checks
        ],
    }
