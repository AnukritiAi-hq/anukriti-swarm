"""``UncertaintyScoringEngine`` + ``UncertaintyAwareReasoningLayer``.

Phase 5, commit 14 of the Evidence Sufficiency Layer brief.

Reads the already-produced coverage + conflict + optional
provenance + optional path-bundle signals and emits a single
``UncertaintyScore`` — one of four closed tiers. A thin policy
wrapper then maps that tier to an ``UncertaintyAction`` the
orchestrator can act on. Both classes are deterministic; no LLM,
no sampling, no randomness. Same input always produces the same
score.

Rationale
---------

Sufficiency (phase 1) already routes on structural facet coverage
+ conflict presence. Uncertainty is a *different* question: "how
confident are we in the conclusion we would otherwise support?"
A run can be SUFFICIENT (all 6 facets covered, no conflict) yet
still carry moderate uncertainty if population support is weak
or the KG path set is thin. The uncertainty layer surfaces that
so the narrative layer can caveat or abstain accordingly.

Closed tiers (brief requirement #18)
------------------------------------

    LOW         high confidence: facets fully covered, no conflict,
                KG pathway (when computed) observed, population
                support strong
    MODERATE    minor weakness: 1 uncertain non-core facet, OR
                soft conflict, OR thin pathway (<2 paths when
                bundle supplied)
    HIGH        substantial weakness: ≥2 uncertain facets, OR
                population facet UNCERTAIN, OR empty KG bundle
                when supplied, OR any MISSING facet still in play
                (shouldn't happen post-sufficiency but we don't
                assume)
    UNSAFE      structural refutation or un-resolvable conflict:
                HARD conflict finding OR refuted path — never
                allow synthesis

Scoring table (closed, deterministic — first match wins)
--------------------------------------------------------

    U1  any HARD conflict finding                     -> UNSAFE
    U2  any MISSING facet (other than CONFLICT_FREE)  -> HIGH
        -- sufficiency would likely have blocked this but the
        -- engine is defensive against partial inputs
    U3  POPULATION facet UNCERTAIN                    -> HIGH
    U4  KG path bundle supplied AND empty             -> HIGH
    U5  ≥2 uncertain facets total                     -> HIGH
    U6  CONFLICT_FREE UNCERTAIN (soft conflict)       -> MODERATE
    U7  exactly 1 uncertain non-core facet            -> MODERATE
        -- non-core meaning not PHENOTYPE / RECOMMENDATION /
        -- POPULATION / CONFLICT_FREE (so ALLELE or CPIC)
    U8  KG path bundle supplied AND only 1 path       -> MODERATE
    U9  otherwise                                     -> LOW

Action mapping (brief requirement #19)
--------------------------------------

    LOW       PROCEED
    MODERATE  PROCEED (with uncertainty payload propagated)
    HIGH      REQUEST_MORE
    UNSAFE    BLOCK

Additional action classes for caller convenience:

    ABSTAIN     the tier layer never emits this itself; downstream
                policies that combine uncertainty with provenance
                state (phase 6 orchestrator) may use it. Provided
                as a closed-enum value so callers don't invent
                their own strings.
    ESCALATE    likewise — reserved for policy composition in
                phase 6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

from core.evidence_sufficiency.conflict.agent import (
    ConflictFinding,
    ConflictSeverity,
)
from core.evidence_sufficiency.coverage.claim_coverage import (
    ClaimCoverageAnalysis,
    ClaimEvidenceFacet,
    FacetCoverageState,
)

# ---------------------------------------------------------------------------
# Closed enums
# ---------------------------------------------------------------------------


class UncertaintyScore(str, Enum):
    """The four allowed uncertainty tiers. Extending is a code change."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNSAFE = "unsafe"


class UncertaintyAction(str, Enum):
    """Closed set of actions downstream policy may take."""

    PROCEED = "proceed"
    REQUEST_MORE = "request_more"
    ABSTAIN = "abstain"
    ESCALATE = "escalate"
    BLOCK = "block"


# ---------------------------------------------------------------------------
# Frozen reading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UncertaintyReading:
    """Frozen per-run uncertainty record.

    Fields
    ------
    score          closed UncertaintyScore
    rule_id        which rule fired (U1..U9) — explicit audit trail
    rationale      human-readable explanation
    action         UncertaintyAction the layer recommends
    coverage_ratio from the ClaimCoverageAnalysis (for convenience;
                   primary record remains in the coverage analysis
                   itself)
    hard_conflict_count
    soft_conflict_count
    pathway_count  0 when no bundle supplied; otherwise the bundle
                   length
    pathway_bundle_supplied
    correlation_id propagated for MCP linkage
    created_at     ISO timestamp
    """

    score: UncertaintyScore
    rule_id: str
    rationale: str
    action: UncertaintyAction
    coverage_ratio: float
    hard_conflict_count: int
    soft_conflict_count: int
    pathway_count: int
    pathway_bundle_supplied: bool
    correlation_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "score": self.score.value,
            "rule_id": self.rule_id,
            "rationale": self.rationale,
            "action": self.action.value,
            "coverage_ratio": round(float(self.coverage_ratio), 4),
            "hard_conflict_count": self.hard_conflict_count,
            "soft_conflict_count": self.soft_conflict_count,
            "pathway_count": self.pathway_count,
            "pathway_bundle_supplied": self.pathway_bundle_supplied,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


@dataclass
class UncertaintyScoringEngine:
    """Deterministic 9-rule uncertainty scorer.

    Stateless; one instance serves many runs. No options — the
    rule table is fixed to keep the score reproducible across
    reviews. Tuning is a code change.
    """

    def score(
        self,
        coverage: ClaimCoverageAnalysis,
        *,
        findings: Iterable[ConflictFinding] = (),
        path_bundle: Sequence | None = None,
    ) -> UncertaintyReading:
        findings_tuple = tuple(findings)
        hard = [f for f in findings_tuple if f.severity is ConflictSeverity.HARD]
        soft = [f for f in findings_tuple if f.severity is ConflictSeverity.SOFT]

        pathway_bundle_supplied = path_bundle is not None
        pathway_count = len(path_bundle) if pathway_bundle_supplied else 0

        score, rule_id, rationale = self._apply_rules(
            coverage=coverage,
            hard=hard,
            soft=soft,
            pathway_bundle_supplied=pathway_bundle_supplied,
            pathway_count=pathway_count,
        )

        return UncertaintyReading(
            score=score,
            rule_id=rule_id,
            rationale=rationale,
            action=_action_for(score),
            coverage_ratio=coverage.coverage_ratio,
            hard_conflict_count=len(hard),
            soft_conflict_count=len(soft),
            pathway_count=pathway_count,
            pathway_bundle_supplied=pathway_bundle_supplied,
            correlation_id=coverage.correlation_id,
        )

    # ------------------------------------------------------------------
    # Rule table
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_rules(
        *,
        coverage: ClaimCoverageAnalysis,
        hard: list,
        soft: list,
        pathway_bundle_supplied: bool,
        pathway_count: int,
    ) -> tuple[UncertaintyScore, str, str]:
        states = coverage.facet_states

        # U1 UNSAFE
        if hard:
            return (
                UncertaintyScore.UNSAFE,
                "U1",
                f"U1: {len(hard)} hard conflict(s) — structural refutation",
            )

        # U2 HIGH — missing facet (excluding CONFLICT_FREE, since U1 ate
        # the hard-conflict case already).
        missing_non_conflict = [
            f for f in coverage.missing_facets if f is not ClaimEvidenceFacet.CONFLICT_FREE
        ]
        if missing_non_conflict:
            names = ", ".join(f.value for f in missing_non_conflict)
            return (
                UncertaintyScore.HIGH,
                "U2",
                f"U2: missing facets — {names}",
            )

        # U3 HIGH — POPULATION uncertain (ancestry-underrepresented)
        if states[ClaimEvidenceFacet.POPULATION] is FacetCoverageState.UNCERTAIN:
            return (
                UncertaintyScore.HIGH,
                "U3",
                f"U3: {coverage.population.value} population support weak",
            )

        # U4 HIGH — empty pathway bundle
        if pathway_bundle_supplied and pathway_count == 0:
            return (
                UncertaintyScore.HIGH,
                "U4",
                "U4: KG path bundle supplied but empty",
            )

        # U5 HIGH — ≥2 uncertain facets total
        if len(coverage.uncertain_facets) >= 2:
            names = ", ".join(f.value for f in coverage.uncertain_facets)
            return (
                UncertaintyScore.HIGH,
                "U5",
                f"U5: multiple uncertain facets — {names}",
            )

        # U6 MODERATE — soft conflict (CONFLICT_FREE uncertain)
        if states[ClaimEvidenceFacet.CONFLICT_FREE] is FacetCoverageState.UNCERTAIN:
            return (
                UncertaintyScore.MODERATE,
                "U6",
                f"U6: {len(soft)} soft conflict(s) recorded",
            )

        # U7 MODERATE — exactly 1 uncertain non-core facet (ALLELE or CPIC)
        non_core_uncertain = [
            f
            for f in coverage.uncertain_facets
            if f in {ClaimEvidenceFacet.ALLELE, ClaimEvidenceFacet.CPIC}
        ]
        if len(non_core_uncertain) == 1:
            return (
                UncertaintyScore.MODERATE,
                "U7",
                f"U7: {non_core_uncertain[0].value} uncertain",
            )

        # U8 MODERATE — thin pathway (1 path only)
        if pathway_bundle_supplied and pathway_count == 1:
            return (
                UncertaintyScore.MODERATE,
                "U8",
                "U8: thin KG pathway (1 path)",
            )

        # U9 LOW
        suffix = f" ({pathway_count} KG paths)" if pathway_bundle_supplied else " (no KG bundle)"
        return (
            UncertaintyScore.LOW,
            "U9",
            f"U9: full coverage, no conflict{suffix}",
        )


# ---------------------------------------------------------------------------
# Reasoning layer (policy mapping)
# ---------------------------------------------------------------------------


def _action_for(score: UncertaintyScore) -> UncertaintyAction:
    """Closed tier -> action mapping. Extending is a code change."""

    if score is UncertaintyScore.UNSAFE:
        return UncertaintyAction.BLOCK
    if score is UncertaintyScore.HIGH:
        return UncertaintyAction.REQUEST_MORE
    # LOW and MODERATE both PROCEED; callers can inspect the reading's
    # .score field to caveat/downgrade MODERATE outputs.
    return UncertaintyAction.PROCEED


@dataclass
class UncertaintyAwareReasoningLayer:
    """Thin policy wrapper over UncertaintyScoringEngine.

    Callers can ``.decide(coverage, findings=..., path_bundle=...)``
    to get an ``UncertaintyReading`` directly, or call
    ``.recommended_action(reading)`` if they already have a
    reading — useful when phase 6 composes multiple uncertainty
    sources.

    Stateless. No configuration knobs. Same tier mapping is used
    everywhere in the codebase via the private ``_action_for``
    helper so policy stays consistent.
    """

    engine: UncertaintyScoringEngine = field(default_factory=UncertaintyScoringEngine)

    def decide(
        self,
        coverage: ClaimCoverageAnalysis,
        *,
        findings: Iterable[ConflictFinding] = (),
        path_bundle: Sequence | None = None,
    ) -> UncertaintyReading:
        return self.engine.score(coverage, findings=findings, path_bundle=path_bundle)

    @staticmethod
    def recommended_action(reading: UncertaintyReading) -> UncertaintyAction:
        """Re-derive action from a reading — useful when a caller is
        about to combine the uncertainty action with other policy
        signals (e.g. in phase 6 the orchestrator OR-ing BLOCK from
        sufficiency + uncertainty). Pure function of ``reading.score``.
        """

        return _action_for(reading.score)


__all__ = [
    "UncertaintyScore",
    "UncertaintyAction",
    "UncertaintyReading",
    "UncertaintyScoringEngine",
    "UncertaintyAwareReasoningLayer",
]
