"""``SufficiencyDecisionEngine`` — deterministic decision layer.

Phase 1 of the Evidence Sufficiency Layer brief, final piece.

This module consumes the outputs of the three analyzers
(``EvidenceCoverageAnalyzer``, ``ProvenanceCoverageTracker``,
``ConflictDetectionAgent``) and produces exactly one of seven closed
decisions. The decision table is fully specified — no LLM, no
probability threshold tuned by a model, no "vibes-based" routing.

The seven decisions (closed set)
--------------------------------

    SUFFICIENT        everything COVERED + no conflicts + provenance
                      complete -> synthesis may run
    PASS_WITH_CAVEAT  everything COVERED but soft conflict downgraded
                      CONFLICT_FREE to UNCERTAIN -> synthesis may run
                      with an explicit caveat propagated to the output
    REQUEST_MORE      addressable gap -> the adaptive retrieval loop
                      (phase 2) should fetch more evidence before
                      re-evaluating; used for ALLELE / CPIC gaps where
                      retrieval is likely to help
    DOWNGRADE         evidence is present but weak (UNCERTAIN facets,
                      soft conflict); synthesis may run but confidence
                      is lowered and the output is labelled
    ESCALATE          ancestry-underrepresented or
                      population-unsupported -> surface to human
                      review; retrieval unlikely to close the gap
    ABSTAIN           provenance attribution is broken -> synthesis is
                      withheld; narrative cannot be audited
    BLOCK             hard conflict or core-facet (phenotype /
                      recommendation) missing -> synthesis MUST NOT
                      run; the safety engine escalates accordingly

Decision rules (priority order)
-------------------------------

Evaluated top-to-bottom; first matching rule wins. This is
deliberately linear and readable — a reviewer can audit policy
changes without reading control flow.

    R1  CONFLICT_FREE == MISSING (hard conflict)   -> BLOCK
    R2  PHENOTYPE == MISSING                       -> BLOCK
    R3  RECOMMENDATION == MISSING                  -> BLOCK
    R4  provenance report present AND incomplete   -> ABSTAIN
    R5  POPULATION == MISSING                      -> ESCALATE
    R6  CPIC == MISSING                            -> REQUEST_MORE
    R7  ALLELE == MISSING                          -> REQUEST_MORE
    R8  RECOMMENDATION == UNCERTAIN                -> DOWNGRADE
    M4  POPULATION == UNCERTAIN with cross-ancestry
        support (opt-in, off by default)           -> EXTRAPOLATION_*
    R9  POPULATION == UNCERTAIN                    -> DOWNGRADE
    R10 any remaining UNCERTAIN facet              -> DOWNGRADE
    R11 CONFLICT_FREE == UNCERTAIN (soft only)     -> PASS_WITH_CAVEAT
    R12 all COVERED, no conflict                   -> SUFFICIENT

Order rationale
---------------

* BLOCK rules come first. Safety trumps everything.
* ABSTAIN comes before ESCALATE / REQUEST_MORE because we cannot
  trust any action (including "ask for more") on an un-attributable
  pipeline — retrieval loops that can't be audited don't help.
* ESCALATE precedes REQUEST_MORE for POPULATION because an
  ancestry-underrepresented population is usually a data-gap
  retrieval can't close (we don't invent it).
* DOWNGRADE rules are specific-to-general (R8-R10). R11 is reached
  only if CONFLICT_FREE is the single UNCERTAIN facet.
* R12 fires iff none of R1-R11 did.

Policy is expressed as one method, ``decide``, returning a
``SufficiencyDecision`` and a human-readable rationale string. The
rationale names which rule fired so the audit trail is explicit.

No configuration knobs. A new decision class is a code change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from core.evidence_sufficiency.conflict.agent import (
    ConflictFinding,
    ConflictSeverity,
)
from core.evidence_sufficiency.coverage.claim_coverage import (
    ClaimCoverageAnalysis,
    ClaimEvidenceFacet,
    FacetCoverageState,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from core.evidence_sufficiency.coverage.provenance_tracker import (
        ProvenanceCoverageReport,
    )

# ---------------------------------------------------------------------------
# Closed-enum decisions
# ---------------------------------------------------------------------------


class SufficiencyDecision(str, Enum):
    """The allowed outcomes. Extending is a code change.

    Seven baseline values (R1-R12 rules). The eighth value
    ``EXTRAPOLATION_WITH_CROSS_ANCESTRY_SUPPORT`` is an optional
    outcome produced only when the engine is constructed with
    ``allow_cross_ancestry_extrapolation=True``. Default behavior
    does not emit this value, preserving the byte-identical
    regression contract for existing consumers.
    """

    SUFFICIENT = "sufficient"
    PASS_WITH_CAVEAT = "pass_with_caveat"
    REQUEST_MORE = "request_more"
    DOWNGRADE = "downgrade"
    ESCALATE = "escalate"
    ABSTAIN = "abstain"
    BLOCK = "block"
    EXTRAPOLATION_WITH_CROSS_ANCESTRY_SUPPORT = "extrapolation_with_cross_ancestry_support"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SufficiencyReport:
    """Frozen per-run decision record.

    Fields
    ------
    decision           one of seven SufficiencyDecision values
    rationale          which rule fired (R1..R12) + natural-language
                       explanation
    coverage           the ClaimCoverageAnalysis this decision read
    provenance         optional ProvenanceCoverageReport; None when
                       the caller didn't pass one in
    findings           tuple of ConflictFindings the decision saw
    correlation_id     propagated from the analysis for MCP linkage
    created_at         ISO timestamp

    Derived helpers
    ---------------
    is_blocking        True when decision is BLOCK or ABSTAIN
    allows_synthesis   True when decision is SUFFICIENT / PASS_WITH_CAVEAT
                       / DOWNGRADE (DOWNGRADE still synthesizes, but
                       with lowered confidence)
    """

    decision: SufficiencyDecision
    rationale: str
    coverage: ClaimCoverageAnalysis
    provenance: ProvenanceCoverageReport | None
    findings: tuple[ConflictFinding, ...]
    correlation_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_blocking(self) -> bool:
        return self.decision in {
            SufficiencyDecision.BLOCK,
            SufficiencyDecision.ABSTAIN,
        }

    @property
    def allows_synthesis(self) -> bool:
        return self.decision in {
            SufficiencyDecision.SUFFICIENT,
            SufficiencyDecision.PASS_WITH_CAVEAT,
            SufficiencyDecision.DOWNGRADE,
            SufficiencyDecision.EXTRAPOLATION_WITH_CROSS_ANCESTRY_SUPPORT,
        }

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "rationale": self.rationale,
            "is_blocking": self.is_blocking,
            "allows_synthesis": self.allows_synthesis,
            "correlation_id": self.correlation_id,
            "coverage": self.coverage.to_dict(),
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "findings": [f.to_dict() for f in self.findings],
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


@dataclass
class SufficiencyDecisionEngine:
    """Deterministic policy engine.

    Every call is a pure function of its inputs plus the engine's
    one construction-time flag (``allow_cross_ancestry_extrapolation``).

    The flag is off by default, preserving the byte-identical
    regression contract for existing consumers. When on, rule M4
    is enabled — a strictly more specific variant of R9 that
    emits ``EXTRAPOLATION_WITH_CROSS_ANCESTRY_SUPPORT`` when
    population evidence is thin but all other facets are solid.

    Design rationale for the flag (rather than making M4
    always-on):

    - Existing consumers (``SufficiencyCheckpoint``,
      ``evidence_sufficiency_demo``, ``evidence_sufficiency_abstention_demo``,
      ``unified_demo``) expect R9 to fire for the canonical AFR +
      CYP2D6 case. Enabling M4 always-on would change their
      output signatures, breaking the byte-identical regression
      contract.
    - Cross-ancestry extrapolation is a *deliberate* epistemic
      posture — "we hedge honestly when cross-ancestry
      consistency is documented." It's the right default for
      cohort-scale simulation scenarios (``demos/cohort_demo.py``),
      but it's a scope extension for the single-scenario flagship
      demos.
    - The off-by-default pattern matches the discipline used for
      every other opt-in capability in the platform
      (``ExecutionCoordinator.sufficiency_checkpoint``,
      ``GeminiOrchestrator.memory_advisor``, and the new
      simulation scope). Opt-in via constructor argument is
      visible in code review; feature flags are not.
    """

    def __init__(self, *, allow_cross_ancestry_extrapolation: bool = False) -> None:
        self.allow_cross_ancestry_extrapolation = allow_cross_ancestry_extrapolation

    def decide(
        self,
        coverage: ClaimCoverageAnalysis,
        *,
        provenance: ProvenanceCoverageReport | None = None,
        findings: Iterable[ConflictFinding] = (),
    ) -> SufficiencyReport:
        """Apply the rule table and return a SufficiencyReport."""

        findings_tuple = tuple(findings)
        decision, rationale = self._apply_rules(coverage, provenance, findings_tuple)

        return SufficiencyReport(
            decision=decision,
            rationale=rationale,
            coverage=coverage,
            provenance=provenance,
            findings=findings_tuple,
            correlation_id=coverage.correlation_id,
        )

    # ------------------------------------------------------------------
    # Rule table
    # ------------------------------------------------------------------

    def _apply_rules(
        self,
        coverage: ClaimCoverageAnalysis,
        provenance: ProvenanceCoverageReport | None,
        findings: tuple[ConflictFinding, ...],
    ) -> tuple[SufficiencyDecision, str]:
        states = coverage.facet_states
        any_hard = any(f.severity is ConflictSeverity.HARD for f in findings)

        # R1 — hard conflict
        if states[ClaimEvidenceFacet.CONFLICT_FREE] is FacetCoverageState.MISSING or any_hard:
            return (
                SufficiencyDecision.BLOCK,
                "R1: hard conflict detected — synthesis blocked",
            )

        # R2 — phenotype missing
        if states[ClaimEvidenceFacet.PHENOTYPE] is FacetCoverageState.MISSING:
            return (
                SufficiencyDecision.BLOCK,
                "R2: phenotype evidence missing — cannot synthesize recommendation",
            )

        # R3 — recommendation missing
        if states[ClaimEvidenceFacet.RECOMMENDATION] is FacetCoverageState.MISSING:
            return (
                SufficiencyDecision.BLOCK,
                "R3: recommendation evidence missing — no actionable output",
            )

        # R4 — provenance report present and incomplete
        if provenance is not None and not provenance.is_complete:
            missing = ", ".join(d.value for d in provenance.missing_dimensions)
            return (
                SufficiencyDecision.ABSTAIN,
                f"R4: provenance attribution incomplete ({missing}) — "
                f"pipeline is not auditable",
            )

        # R5 — population missing
        if states[ClaimEvidenceFacet.POPULATION] is FacetCoverageState.MISSING:
            return (
                SufficiencyDecision.ESCALATE,
                f"R5: {coverage.population.value} population evidence missing — "
                f"escalating for ancestry review",
            )

        # R6 — CPIC missing
        if states[ClaimEvidenceFacet.CPIC] is FacetCoverageState.MISSING:
            return (
                SufficiencyDecision.REQUEST_MORE,
                f"R6: CPIC guideline for {coverage.gene}+{coverage.drug} not in "
                f"retrieval set — request additional evidence",
            )

        # R7 — allele missing
        if states[ClaimEvidenceFacet.ALLELE] is FacetCoverageState.MISSING:
            return (
                SufficiencyDecision.REQUEST_MORE,
                f"R7: no allele-bearing source cites {coverage.gene} — "
                f"request additional evidence",
            )

        # R8 — recommendation uncertain
        if states[ClaimEvidenceFacet.RECOMMENDATION] is FacetCoverageState.UNCERTAIN:
            return (
                SufficiencyDecision.DOWNGRADE,
                "R8: recommendation weakly cited — confidence lowered",
            )

        # M4 — cross-ancestry extrapolation hedge (opt-in, off by default)
        #
        # Preconditions: POPULATION is UNCERTAIN, but ALLELE +
        # PHENOTYPE + CPIC + RECOMMENDATION are all COVERED. That
        # combination means direct population evidence is thin but
        # everything else is solid — we have enough cross-ancestry
        # context to hedge honestly rather than just downgrade.
        #
        # When the flag is off (default), this rule is skipped and
        # R9 fires as before — preserving the byte-identical
        # regression contract for existing demos.
        if (
            self.allow_cross_ancestry_extrapolation
            and states[ClaimEvidenceFacet.POPULATION] is FacetCoverageState.UNCERTAIN
            and states[ClaimEvidenceFacet.ALLELE] is FacetCoverageState.COVERED
            and states[ClaimEvidenceFacet.PHENOTYPE] is FacetCoverageState.COVERED
            and states[ClaimEvidenceFacet.CPIC] is FacetCoverageState.COVERED
            and states[ClaimEvidenceFacet.RECOMMENDATION] is FacetCoverageState.COVERED
        ):
            return (
                SufficiencyDecision.EXTRAPOLATION_WITH_CROSS_ANCESTRY_SUPPORT,
                f"M4: {coverage.population.value} direct population evidence thin "
                f"but ALLELE + PHENOTYPE + CPIC + RECOMMENDATION all covered — "
                f"cross-ancestry extrapolation hedge applied",
            )

        # R9 — population uncertain
        if states[ClaimEvidenceFacet.POPULATION] is FacetCoverageState.UNCERTAIN:
            return (
                SufficiencyDecision.DOWNGRADE,
                f"R9: {coverage.population.value} population support weak — " f"confidence lowered",
            )

        # R10 — any remaining UNCERTAIN
        other_uncertain = [
            f
            for f in coverage.uncertain_facets
            if f
            not in {
                ClaimEvidenceFacet.RECOMMENDATION,
                ClaimEvidenceFacet.POPULATION,
                ClaimEvidenceFacet.CONFLICT_FREE,
            }
        ]
        if other_uncertain:
            names = ", ".join(f.value for f in other_uncertain)
            return (
                SufficiencyDecision.DOWNGRADE,
                f"R10: uncertain facets ({names}) — confidence lowered",
            )

        # R11 — only CONFLICT_FREE uncertain (soft conflict)
        if states[ClaimEvidenceFacet.CONFLICT_FREE] is FacetCoverageState.UNCERTAIN:
            return (
                SufficiencyDecision.PASS_WITH_CAVEAT,
                "R11: soft conflict detected — synthesis proceeds with caveat",
            )

        # R12 — sufficient
        return (
            SufficiencyDecision.SUFFICIENT,
            "R12: all facets covered, no conflict, provenance complete",
        )


__all__ = [
    "SufficiencyDecision",
    "SufficiencyReport",
    "SufficiencyDecisionEngine",
]
