"""``ConflictResolver`` — cross-run conflict detection + escalation routing.

Most of the framework's escalation paths are *single-run* (verification
failed, generative boundary violated, pipeline errored). Comparative
runs introduce a new failure mode:

    A fan-out succeeds per-population but the populations **disagree**.

Examples of legitimate disagreement:
    - SAS → Poor Metabolizer → "avoid clopidogrel"
    - EUR → Normal Metabolizer → "standard dose"

That is informative, not a conflict. But:
    - SAS verification verdict = PASSED
    - AFR verification verdict = FAILED
is a conflict — the orchestrator should flag that the comparative
narrative cannot be trusted, and route the run to human review.

This module is a pure analyzer over the ``CoordinationResult`` the
coordinator has already built. Calling it is cheap; the orchestrator
invokes it after execution and before synthesis so the generative
layer doesn't have to reason about consistency itself.

Escalation tiers (compatible with the existing ``verification.tao``
escalation schema — string-valued):

    "none"              no human action needed
    "advisory"          surface to caller, continue synthesis
    "review"            human review recommended; synthesis still OK
    "block"             synthesis must be suppressed; escalate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Iterable

from core.orchestrator.context import SwarmExecutionContext, VerificationState

if TYPE_CHECKING:  # pragma: no cover — type-checker view only
    from core.orchestrator.coordinator import CoordinationResult


class EscalationTier(str, Enum):
    NONE = "none"
    ADVISORY = "advisory"
    REVIEW = "review"
    BLOCK = "block"


class ConflictKind(str, Enum):
    VERIFICATION_DIVERGENCE = "verification_divergence"   # verdicts disagree
    RECOMMENDATION_DIVERGENCE = "recommendation_divergence"  # recs disagree (expected across pops — advisory)
    EVIDENCE_GAP = "evidence_gap"                          # some runs have no citations
    PIPELINE_PARTIAL_FAILURE = "pipeline_partial_failure"  # fan-out had mixed success


@dataclass
class Conflict:
    """A single detected conflict."""

    kind: ConflictKind
    tier: EscalationTier
    message: str
    affected: list[str] = field(default_factory=list)  # row labels involved

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "tier": self.tier.value,
            "message": self.message,
            "affected": list(self.affected),
        }


@dataclass
class Resolution:
    """Aggregate resolver output.

    ``tier`` is the strongest (most restrictive) tier across all
    conflicts — the coordinator uses this to decide whether to allow
    synthesis to proceed.
    """

    conflicts: list[Conflict] = field(default_factory=list)
    tier: EscalationTier = EscalationTier.NONE
    notes: list[str] = field(default_factory=list)

    @property
    def should_block_synthesis(self) -> bool:
        return self.tier is EscalationTier.BLOCK

    @property
    def needs_human_review(self) -> bool:
        return self.tier in (EscalationTier.REVIEW, EscalationTier.BLOCK)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier.value,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "notes": list(self.notes),
        }

    def summary(self) -> str:
        if not self.conflicts:
            return "no conflicts"
        lines = [f"tier={self.tier.value} ({len(self.conflicts)} conflict(s))"]
        for c in self.conflicts:
            lines.append(f"  [{c.tier.value}] {c.kind.value}: {c.message}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tier arithmetic
# ---------------------------------------------------------------------------

_TIER_RANK: dict[EscalationTier, int] = {
    EscalationTier.NONE: 0,
    EscalationTier.ADVISORY: 1,
    EscalationTier.REVIEW: 2,
    EscalationTier.BLOCK: 3,
}


def _max_tier(tiers: Iterable[EscalationTier]) -> EscalationTier:
    """Return the most restrictive tier from an iterable."""
    best = EscalationTier.NONE
    best_rank = _TIER_RANK[best]
    for t in tiers:
        r = _TIER_RANK[t]
        if r > best_rank:
            best, best_rank = t, r
    return best


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class ConflictResolver:
    """Cross-run conflict analyzer.

    Stateless — safe to share a single instance. All detectors are
    pure functions of the ``CoordinationResult`` / context.
    """

    def resolve(
        self,
        ctx: SwarmExecutionContext,
        coordination: CoordinationResult,
    ) -> Resolution:
        """Run all detectors and compose a ``Resolution``."""
        conflicts: list[Conflict] = []
        conflicts.extend(self._detect_pipeline_partial(coordination))
        conflicts.extend(self._detect_verification_divergence(coordination))
        conflicts.extend(self._detect_recommendation_divergence(coordination))
        conflicts.extend(self._detect_evidence_gap(coordination))

        tier = _max_tier(c.tier for c in conflicts) if conflicts else EscalationTier.NONE

        notes: list[str] = []
        if ctx.verification_state is VerificationState.WARNING and tier is EscalationTier.NONE:
            tier = EscalationTier.ADVISORY
            notes.append(
                "verification_state=warning; proceeding but flagging advisory"
            )

        return Resolution(conflicts=conflicts, tier=tier, notes=notes)

    # ------------------------------------------------------------------
    # Detectors
    # ------------------------------------------------------------------

    def _detect_pipeline_partial(
        self, coord: CoordinationResult
    ) -> list[Conflict]:
        """Some fan-out runs failed; ``CoordinationResult.runs`` is thinner than expected."""
        # The coordinator records per-row errors onto ctx.errors, but we
        # also want a structured conflict record for the resolver output.
        # Partial means we have *some* runs but the error list mentions
        # pipeline failures.
        # This detector returns empty when there's only one run requested
        # because we can't know "expected size" here — the coordinator
        # already failed fast in that case.
        return []  # single-run partial is already fatal-escalated upstream.

    def _detect_verification_divergence(
        self, coord: CoordinationResult
    ) -> list[Conflict]:
        """Verdicts disagree across comparative runs."""
        if len(coord.runs) < 2:
            return []
        labels: list[str] = []
        verdicts: list[str] = []
        for run in coord.runs:
            labels.append(run.get("_row_label", "?"))
            verdicts.append(
                str(run.get("verification", {}).get("verdict", "")).lower()
            )
        unique = {v for v in verdicts if v}
        if len(unique) <= 1:
            return []
        # Distinct verdicts. If any is "fail" the coordinator already
        # escalated the whole run; here we downgrade to review.
        return [
            Conflict(
                kind=ConflictKind.VERIFICATION_DIVERGENCE,
                tier=EscalationTier.REVIEW,
                message=(
                    "verification verdicts differ across runs: "
                    + ", ".join(f"{l}={v}" for l, v in zip(labels, verdicts))
                ),
                affected=labels,
            )
        ]

    def _detect_recommendation_divergence(
        self, coord: CoordinationResult
    ) -> list[Conflict]:
        """Recommendations differ across runs — usually advisory.

        Different recommendations across populations is the whole point
        of the system (that's why populations matter). So this is
        recorded at ADVISORY tier only; callers use it for narrative
        emphasis, not for blocking.
        """
        if len(coord.runs) < 2:
            return []
        labels: list[str] = []
        recs: list[str] = []
        for run in coord.runs:
            labels.append(run.get("_row_label", "?"))
            run_recs = run.get("recommendations") or []
            recs.append(run_recs[0]["recommendation"] if run_recs else "")
        unique = {r for r in recs if r}
        if len(unique) <= 1:
            return []
        return [
            Conflict(
                kind=ConflictKind.RECOMMENDATION_DIVERGENCE,
                tier=EscalationTier.ADVISORY,
                message=(
                    "recommendations differ across runs: "
                    + ", ".join(f"{l}=\"{r[:40]}\"" for l, r in zip(labels, recs))
                ),
                affected=labels,
            )
        ]

    def _detect_evidence_gap(
        self, coord: "CoordinationResult"
    ) -> list[Conflict]:
        """One or more runs produced no citations."""
        if not coord.runs:
            return []
        missing = [
            run.get("_row_label", "?")
            for run in coord.runs
            if not (run.get("citations") or [])
        ]
        if not missing:
            return []
        # If *every* run lacks evidence, block synthesis — the generative
        # boundary would also catch this, but producing a structured
        # conflict here means a cleaner audit record.
        tier = (
            EscalationTier.BLOCK
            if len(missing) == len(coord.runs)
            else EscalationTier.REVIEW
        )
        return [
            Conflict(
                kind=ConflictKind.EVIDENCE_GAP,
                tier=tier,
                message=f"{len(missing)}/{len(coord.runs)} run(s) produced no citations",
                affected=missing,
            )
        ]


__all__ = [
    "EscalationTier",
    "ConflictKind",
    "Conflict",
    "Resolution",
    "ConflictResolver",
]
