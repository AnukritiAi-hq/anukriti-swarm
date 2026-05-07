"""Verification engine orchestrating all checks.

Runs the full verification pipeline on an agent output:
1. Execute all applicable checks
2. Compute propagated confidence
3. Assess escalation tier
4. Generate verification report

The engine is the single entry point for verification — all agent
outputs pass through here before reaching the narrative layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from verification.escalation.tao import EscalationDecision, assess_escalation
from verification.rules.checks import (
    CheckResult,
    Verdict,
    check_deterministic_boundary,
    check_evidence_grounding,
    check_guideline_conflict,
    check_hallucination_hooks,
    check_provenance,
    check_sparse_population_data,
)
from verification.rules.confidence import ConfidenceScore, propagate_confidence


# Known entities for hallucination detection
KNOWN_GENES = {"CYP2D6", "CYP2C19", "CYP2C9", "HLA-B", "HLA-A", "TPMT", "DPYD", "VKORC1", "SLCO1B1"}
KNOWN_DRUGS = {
    "codeine", "tamoxifen", "clopidogrel", "carbamazepine", "oxcarbazepine",
    "phenytoin", "warfarin", "omeprazole", "escitalopram", "tramadol",
    "prasugrel", "ticagrelor", "amitriptyline",
}


@dataclass
class VerificationReport:
    """Complete verification report for an agent output."""

    agent_id: str
    gene: str | None
    checks: list[CheckResult] = field(default_factory=list)
    confidence: ConfidenceScore | None = None
    escalation: EscalationDecision | None = None
    overall_verdict: Verdict = Verdict.PASS
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def passed(self) -> bool:
        return self.overall_verdict == Verdict.PASS

    @property
    def needs_escalation(self) -> bool:
        return self.escalation is not None and self.escalation.tier.value != "autonomous"


class VerificationEngine:
    """Orchestrates all verification checks on agent outputs.

    Usage:
        engine = VerificationEngine()
        report = engine.verify(output)
        if report.needs_escalation:
            handle_escalation(report.escalation)
    """

    def verify(
        self,
        output: dict[str, Any],
        claims: list[dict[str, Any]] | None = None,
        recommendations: list[dict[str, Any]] | None = None,
        stage_confidences: dict[str, float] | None = None,
    ) -> VerificationReport:
        """Run full verification pipeline on an output."""
        checks: list[CheckResult] = []

        # 1. Evidence grounding
        if claims is not None:
            checks.append(check_evidence_grounding(claims))

        # 2. Deterministic boundary
        checks.append(check_deterministic_boundary(output))

        # 3. Provenance
        checks.append(check_provenance(output))

        # 4. Guideline conflicts
        if recommendations:
            checks.append(check_guideline_conflict(recommendations))

        # 5. Sparse population data
        population = output.get("population")
        if population:
            checks.append(check_sparse_population_data(
                population=population,
                sample_n=output.get("sample_n"),
                frequency=output.get("frequency"),
            ))

        # 6. Hallucination hooks
        checks.append(check_hallucination_hooks(output, KNOWN_GENES, KNOWN_DRUGS))

        # Compute confidence
        confidences = stage_confidences or {"output": output.get("confidence", 1.0)}
        confidence = propagate_confidence(confidences)

        # Assess escalation
        escalation = assess_escalation(checks, confidence)

        # Overall verdict
        if any(c.verdict == Verdict.FAIL for c in checks):
            overall = Verdict.FAIL
        elif any(c.verdict == Verdict.WARN for c in checks):
            overall = Verdict.WARN
        else:
            overall = Verdict.PASS

        return VerificationReport(
            agent_id=output.get("agent_id", "unknown"),
            gene=output.get("gene"),
            checks=checks,
            confidence=confidence,
            escalation=escalation,
            overall_verdict=overall,
        )
