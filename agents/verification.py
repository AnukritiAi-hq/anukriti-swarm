"""Anukriti Swarm — Verification Agent.

Validates upstream results before narrative generation.
Checks: source attribution, confidence thresholds, evidence support.
"""

from __future__ import annotations

from agents.base import BaseAgent
from agents.models import AgentResult, AgentType, ExecutionMode, PharmacogeneResult
from agents.state import SwarmState


class VerificationAgent(BaseAgent):
    """Verification agent — safety gate before narrative generation.

    Runs validation checks on pharmacogene results and evidence:
    1. Source attribution present
    2. Confidence above threshold (0.7)
    3. Evidence exists for each gene finding
    """

    CONFIDENCE_THRESHOLD = 0.7

    @property
    def agent_type(self) -> AgentType:
        return AgentType.VERIFICATION

    @property
    def execution_mode(self) -> ExecutionMode:
        return ExecutionMode.DETERMINISTIC

    def execute(self, state: SwarmState) -> SwarmState:
        """Verify all pharmacogene results against evidence."""
        pharmacogene_results = state.get("pharmacogene_results", [])
        evidence = state.get("evidence", [])

        verification_results = []
        evidence_genes = {e["gene"] for e in evidence}

        for pgx in pharmacogene_results:
            checks = self._run_checks(pgx, evidence_genes)
            verification_results.append(checks)

        return {"verification_results": verification_results}  # type: ignore[return-value]

    def _run_checks(
        self, pgx: PharmacogeneResult, evidence_genes: set[str]
    ) -> AgentResult:
        """Run verification checks on a single pharmacogene result."""
        checks_passed = []
        checks_failed = []

        # Check 1: Source attribution
        if pgx.guideline_source:
            checks_passed.append("source_attribution")
        else:
            checks_failed.append("source_attribution")

        # Check 2: Confidence threshold
        if pgx.confidence >= self.CONFIDENCE_THRESHOLD:
            checks_passed.append("confidence_threshold")
        else:
            checks_failed.append("confidence_threshold")

        # Check 3: Evidence support
        if pgx.gene in evidence_genes:
            checks_passed.append("evidence_support")
        else:
            checks_failed.append("evidence_support")

        verdict = "pass" if not checks_failed else "fail"

        return self.create_result(
            task_id=f"verify_{pgx.gene}",
            output={
                "gene": pgx.gene,
                "checks_passed": checks_passed,
                "checks_failed": checks_failed,
                "verdict": verdict,
            },
            confidence=1.0 if verdict == "pass" else 0.5,
            sources=["verification_engine"],
        )
