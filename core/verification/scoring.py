"""``VerificationScore`` — 5-tier scoring for biomedical outputs.

Requirement #4 of the deterministic safety brief: every verification
outcome classifies into exactly one of

    grounded            every claim cites evidence + rule + source,
                        verification passed, confidence ≥ HIGH
    partially_grounded  some claims cite evidence, but at least one
                        is missing a source / rule / confidence ≥
                        MODERATE
    unverified          claims have no deterministic grounding at
                        all; output is advisory only
    conflicting         at least two validators disagree (evidence
                        says X, rule says Y) or a ``guideline_conflict``
                        check failed
    unsafe              a hard-stop condition fires — hallucinated
                        entity, blocked drug-gene interaction, missing
                        evidence for a high-risk recommendation

The score is **not** a replacement for the existing
``Verdict`` enum in ``verification/rules/checks.py``; it's a
higher-level classification that aggregates multiple checks into a
single delivery decision. The ``SafetyConstraintEngine`` consumes
it to decide whether to ``BLOCK`` an output.

Contract
--------
The score is a **pure function** of ``CheckResult`` list + optional
``ConfidenceScore``. No MCP lookups, no network. Same inputs →
same score, always. This makes the scoring trivially testable and
lets the escalation workflow reason about tier transitions.

Mapping from existing check verdicts to the 5 tiers::

    FAIL on provenance / evidence_grounding   → unverified or unsafe
    FAIL on guideline_conflict                → conflicting
    FAIL on hallucination_detection           → unsafe
    any WARN + HIGH confidence                → partially_grounded
    all PASS + HIGH confidence                → grounded
    all PASS + < HIGH confidence              → partially_grounded
    no checks or all SKIP                     → unverified

The tier order is **monotonic in safety**: classify_score returns
the *worst* tier encountered across all signals. A single unsafe
signal anywhere in the check list pulls the whole output down to
``unsafe`` — no amount of grounded claims can override it. This
matches the safety-engineering rule that a single broken safety
constraint invalidates the delivery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from verification.rules.checks import CheckResult, Verdict
from verification.rules.confidence import (
    ConfidenceLevel,
    ConfidenceScore,
    classify_confidence,
)


class VerificationTier(str, Enum):
    """The 5 scoring tiers from the safety brief.

    Ordering (worst → best) determines monotonic aggregation:
    ``UNSAFE > CONFLICTING > UNVERIFIED > PARTIALLY_GROUNDED > GROUNDED``.
    Use ``worse_of(a, b)`` to fold two tiers — the ``unsafe``
    floor wins.
    """

    GROUNDED = "grounded"
    PARTIALLY_GROUNDED = "partially_grounded"
    UNVERIFIED = "unverified"
    CONFLICTING = "conflicting"
    UNSAFE = "unsafe"


# Lower index = safer. Used by ``worse_of``.
_TIER_RANK: dict[VerificationTier, int] = {
    VerificationTier.GROUNDED: 0,
    VerificationTier.PARTIALLY_GROUNDED: 1,
    VerificationTier.UNVERIFIED: 2,
    VerificationTier.CONFLICTING: 3,
    VerificationTier.UNSAFE: 4,
}

# Checks whose FAIL escalates directly to UNSAFE (hard-stop signals).
# These are the checks that indicate a safety-critical breakdown —
# unknown drug/gene, absence of required provenance on a deterministic
# claim. Everything else gets classified by the lesser-severity rules
# below.
_UNSAFE_ON_FAIL: frozenset[str] = frozenset({
    "hallucination_detection",
    # provenance FAIL is treated as UNVERIFIED by default — missing
    # provenance means we can't tell if it's safe or not, which is
    # weaker than a known-unsafe signal. Callers that want a stricter
    # posture can pass ``strict_provenance=True`` to classify_score.
})

# Checks whose FAIL means "we have two disagreeing sources".
_CONFLICTING_ON_FAIL: frozenset[str] = frozenset({
    "guideline_conflict",
})


@dataclass(frozen=True)
class VerificationScore:
    """Structured result of a verification scoring pass.

    Frozen because once scored an output's tier is part of the
    permanent audit trail; mutation would break downstream trust.
    Use ``to_dict()`` before persisting through MCP.
    """

    tier: VerificationTier
    reason: str
    confidence: float            # propagated final confidence [0.0, 1.0]
    confidence_level: ConfidenceLevel
    passing_checks: tuple[str, ...] = ()
    warning_checks: tuple[str, ...] = ()
    failing_checks: tuple[str, ...] = ()
    blocking_check: str = ""     # which check forced a CONFLICTING / UNSAFE tier
    scored_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_deliverable(self) -> bool:
        """True when the output is safe to surface to a user.

        ``grounded`` and ``partially_grounded`` deliver (with caveats
        on the latter). Everything else blocks or escalates.
        """
        return self.tier in (
            VerificationTier.GROUNDED,
            VerificationTier.PARTIALLY_GROUNDED,
        )

    @property
    def is_blocking(self) -> bool:
        """True when the safety gate must block delivery outright."""
        return self.tier in (VerificationTier.CONFLICTING, VerificationTier.UNSAFE)

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict form for MCP persistence / JSON dashboards."""
        return {
            "tier": self.tier.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "passing_checks": list(self.passing_checks),
            "warning_checks": list(self.warning_checks),
            "failing_checks": list(self.failing_checks),
            "blocking_check": self.blocking_check,
            "is_deliverable": self.is_deliverable,
            "is_blocking": self.is_blocking,
            "scored_at": self.scored_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Pure classifier — the only public function. Everything above is shape.
# ---------------------------------------------------------------------------


def classify_score(
    checks: list[CheckResult],
    *,
    confidence: ConfidenceScore | None = None,
    strict_provenance: bool = False,
) -> VerificationScore:
    """Map check results + confidence onto one of the 5 tiers.

    Algorithm (monotonic, worst-wins):

        1. If any unsafe-on-fail check FAILs → UNSAFE (hard stop).
        2. Else if any conflicting-on-fail check FAILs → CONFLICTING.
        3. Else if any remaining check FAILs → UNVERIFIED.
        4. Else if strict_provenance and a ``provenance`` check is
           missing / SKIPped → UNVERIFIED (we can't attest).
        5. Else if any WARN or confidence below HIGH → PARTIALLY_GROUNDED.
        6. Else → GROUNDED.

    Ties between "could be CONFLICTING" and "could be UNSAFE" always
    resolve to UNSAFE — conflicts are resolvable by a second opinion,
    unsafe outputs aren't.

    ``confidence`` is optional so the scorer can run on just a check
    list. When supplied it can demote a GROUNDED tier to
    PARTIALLY_GROUNDED if confidence dropped below HIGH.
    """
    # Bucket checks by verdict for the summary fields.
    passing = tuple(c.check_name for c in checks if c.verdict == Verdict.PASS)
    warning = tuple(c.check_name for c in checks if c.verdict == Verdict.WARN)
    failing = tuple(c.check_name for c in checks if c.verdict == Verdict.FAIL)
    skipped = {c.check_name for c in checks if c.verdict == Verdict.SKIP}

    conf_value = confidence.value if confidence is not None else 1.0
    conf_level = (
        confidence.level if confidence is not None
        else classify_confidence(conf_value)
    )

    # Rule 1 — hard-stop UNSAFE
    for c in checks:
        if c.verdict == Verdict.FAIL and c.check_name in _UNSAFE_ON_FAIL:
            return VerificationScore(
                tier=VerificationTier.UNSAFE,
                reason=(
                    f"Hard-stop safety check failed ({c.check_name}): {c.reason}"
                ),
                confidence=conf_value,
                confidence_level=conf_level,
                passing_checks=passing,
                warning_checks=warning,
                failing_checks=failing,
                blocking_check=c.check_name,
            )

    # Rule 2 — CONFLICTING
    for c in checks:
        if c.verdict == Verdict.FAIL and c.check_name in _CONFLICTING_ON_FAIL:
            return VerificationScore(
                tier=VerificationTier.CONFLICTING,
                reason=(
                    f"Conflict detected ({c.check_name}): {c.reason}"
                ),
                confidence=conf_value,
                confidence_level=conf_level,
                passing_checks=passing,
                warning_checks=warning,
                failing_checks=failing,
                blocking_check=c.check_name,
            )

    # Rule 3 — any other FAIL → UNVERIFIED
    if failing:
        first = next(c for c in checks if c.verdict == Verdict.FAIL)
        return VerificationScore(
            tier=VerificationTier.UNVERIFIED,
            reason=(
                f"Verification failed ({first.check_name}): {first.reason}"
            ),
            confidence=conf_value,
            confidence_level=conf_level,
            passing_checks=passing,
            warning_checks=warning,
            failing_checks=failing,
            blocking_check=first.check_name,
        )

    # Rule 4 — strict provenance mode
    if strict_provenance and ("provenance" in skipped or not any(
        c.check_name == "provenance" for c in checks
    )):
        return VerificationScore(
            tier=VerificationTier.UNVERIFIED,
            reason="Strict provenance mode: provenance check missing / skipped.",
            confidence=conf_value,
            confidence_level=conf_level,
            passing_checks=passing,
            warning_checks=warning,
            failing_checks=failing,
            blocking_check="provenance",
        )

    # Rule 5 — WARNs or sub-HIGH confidence → PARTIALLY_GROUNDED
    if warning or conf_level != ConfidenceLevel.HIGH:
        reason_parts: list[str] = []
        if warning:
            reason_parts.append(f"{len(warning)} warning check(s): {', '.join(warning)}")
        if conf_level != ConfidenceLevel.HIGH:
            reason_parts.append(f"confidence={conf_level.value} ({conf_value:.2f})")
        return VerificationScore(
            tier=VerificationTier.PARTIALLY_GROUNDED,
            reason="; ".join(reason_parts) or "Partial grounding",
            confidence=conf_value,
            confidence_level=conf_level,
            passing_checks=passing,
            warning_checks=warning,
            failing_checks=failing,
        )

    # Rule 6 — GROUNDED
    return VerificationScore(
        tier=VerificationTier.GROUNDED,
        reason=(
            f"All {len(passing)} check(s) passed with "
            f"{conf_level.value} confidence ({conf_value:.2f})."
        ),
        confidence=conf_value,
        confidence_level=conf_level,
        passing_checks=passing,
        warning_checks=warning,
        failing_checks=failing,
    )


def worse_of(a: VerificationTier, b: VerificationTier) -> VerificationTier:
    """Return the less-safe of two tiers.

    Used when folding per-claim scores into a per-run aggregate —
    the run's tier is the worst of any claim's tier, so a single
    UNSAFE claim anywhere in the run blocks the whole delivery.
    """
    return a if _TIER_RANK[a] >= _TIER_RANK[b] else b


__all__ = [
    "VerificationTier",
    "VerificationScore",
    "classify_score",
    "worse_of",
]
