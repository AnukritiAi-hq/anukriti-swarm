"""TAO-inspired escalation logic.

Think-Act-Observe (TAO) pattern adapted for pharmacogenomic safety:
- THINK: assess risk level from verification results
- ACT: route to appropriate handling (autonomous, review, escalate)
- OBSERVE: log decision and rationale for audit

Escalation tiers:
- LOW RISK: autonomous delivery (all checks pass, high confidence)
- MEDIUM RISK: multi-agent review (warnings present, moderate confidence)
- HIGH RISK: human escalation marker (failures present, low confidence)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from verification.rules.checks import CheckResult, Verdict
from verification.rules.confidence import ConfidenceLevel, ConfidenceScore


class EscalationTier(str, Enum):
    """TAO escalation tier determining handling path."""

    AUTONOMOUS = "autonomous"       # Low risk — deliver directly
    MULTI_AGENT_REVIEW = "multi_agent_review"  # Medium risk — additional agent validation
    HUMAN_ESCALATION = "human_escalation"      # High risk — flag for human review


@dataclass(frozen=True)
class EscalationDecision:
    """The result of TAO escalation assessment."""

    tier: EscalationTier
    reason: str
    confidence: ConfidenceScore
    check_summary: dict[str, int]   # verdict → count
    blocking_checks: list[str]      # Check names that caused escalation
    recommended_action: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def assess_escalation(
    checks: list[CheckResult], confidence: ConfidenceScore
) -> EscalationDecision:
    """TAO THINK: Assess risk and determine escalation tier.

    Rules:
    - Any FAIL + confidence < MODERATE → HUMAN_ESCALATION
    - Any FAIL + confidence ≥ MODERATE → MULTI_AGENT_REVIEW
    - Any WARN + confidence < HIGH → MULTI_AGENT_REVIEW
    - All PASS + confidence ≥ HIGH → AUTONOMOUS
    """
    summary = _summarize_checks(checks)
    blocking = [c.check_name for c in checks if c.verdict == Verdict.FAIL]

    # THINK: evaluate risk
    has_failures = summary.get("fail", 0) > 0
    has_warnings = summary.get("warn", 0) > 0

    # ACT: determine tier
    if has_failures and confidence.level in (ConfidenceLevel.LOW, ConfidenceLevel.INSUFFICIENT):
        tier = EscalationTier.HUMAN_ESCALATION
        reason = f"Verification failures ({summary['fail']}) with {confidence.level.value} confidence."
        action = "Flag for human pharmacogenomics expert review. Do not deliver autonomously."
    elif has_failures:
        tier = EscalationTier.MULTI_AGENT_REVIEW
        reason = f"Verification failures ({summary['fail']}) but confidence is {confidence.level.value}."
        action = "Route to verification agent for secondary review. May resolve with additional evidence."
    elif has_warnings and confidence.level != ConfidenceLevel.HIGH:
        tier = EscalationTier.MULTI_AGENT_REVIEW
        reason = f"Warnings ({summary['warn']}) with {confidence.level.value} confidence."
        action = "Additional agent review recommended. Deliver with caveats if review passes."
    else:
        tier = EscalationTier.AUTONOMOUS
        reason = "All checks pass with adequate confidence."
        action = "Deliver results autonomously."

    # OBSERVE: return structured decision
    return EscalationDecision(
        tier=tier,
        reason=reason,
        confidence=confidence,
        check_summary=summary,
        blocking_checks=blocking,
        recommended_action=action,
    )


def _summarize_checks(checks: list[CheckResult]) -> dict[str, int]:
    """Count verdicts across all checks."""
    summary: dict[str, int] = {"pass": 0, "fail": 0, "warn": 0, "skip": 0}
    for c in checks:
        summary[c.verdict.value] = summary.get(c.verdict.value, 0) + 1
    return summary
