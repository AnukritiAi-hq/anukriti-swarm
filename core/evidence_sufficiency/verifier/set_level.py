"""``SetLevelEvidenceVerifier`` — compositional 10-rule set-level verdict.

Phase 4, commit 13 of the Evidence Sufficiency Layer brief.

Reads the already-produced outputs of the coverage analyzer + the
conflict detector + (optionally) a KG path bundle, and emits a
single ``EvidenceVerificationResult`` over the whole evidence
bundle — exactly one of the five closed ``EvidenceVerdict``
values. Pure function; no LLM, no document re-open, no rule
re-derivation.

This is the SURE-RAG move: judge the evidence set *jointly*
rather than one claim at a time. Where the claim validator is
local ("does this claim cite something"), the set-level verifier
is global ("does the bundle, taken together, support the
conclusion").

Rule table (V1 .. V10, priority order — first match wins)
---------------------------------------------------------

    V1  hard RECOMMENDATION_CLASH with a named invertor
        (one side AVOID/CONTRAINDICATED, other side USE) ->
        REFUTED. We can NAME the refuting signal.

    V2  any other HARD conflict finding                         ->
        CONFLICTING. We cannot pick a side.

    V3  PHENOTYPE facet MISSING                                 ->
        INSUFFICIENT.

    V4  RECOMMENDATION facet MISSING                            ->
        INSUFFICIENT.

    V5  any other MISSING facet (ALLELE / CPIC / POPULATION)    ->
        INSUFFICIENT. CONFLICT_FREE MISSING is unreachable
        because V1/V2 handle hard conflicts first.

    V6  KG path bundle supplied AND empty                       ->
        UNCERTAIN. Pathway reachability is a first-class signal;
        if the caller passed a bundle and found nothing, we
        cannot claim the pathway is supported.

    V7  POPULATION facet UNCERTAIN                              ->
        UNCERTAIN. Ancestry underrepresentation — epistemic.

    V8  any other UNCERTAIN facet                               ->
        UNCERTAIN.

    V9  CONFLICT_FREE UNCERTAIN (soft conflict only)            ->
        UNCERTAIN.

    V10 all COVERED, no HARD conflict, pathway nonempty when
        bundle supplied                                         ->
        SUPPORTED.

Pathway semantics
-----------------

When the caller supplies a KG path bundle (tuple of ``GraphPath``),
the verifier treats an empty bundle as a real signal (V6). When the
caller omits the bundle (``path_bundle=()`` by default), pathway
completeness is simply not a driver — V10 doesn't require it and
V6 cannot fire. That keeps the verifier useful even before the
``GraphRetriever`` body ships.

The verifier does NOT re-execute retrieval, does NOT run graph
reasoning, and does NOT open documents. It reads what the caller
has already produced and applies the table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.evidence_sufficiency.conflict.agent import (
    ConflictFinding,
    ConflictKind,
    ConflictSeverity,
    RecommendationAction,
    classify_action,
)
from core.evidence_sufficiency.coverage.claim_coverage import (
    ClaimCoverageAnalysis,
    ClaimEvidenceFacet,
    FacetCoverageState,
)
from core.evidence_sufficiency.verifier.result import (
    EvidenceVerdict,
    EvidenceVerificationResult,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


@dataclass
class SetLevelEvidenceVerifier:
    """Deterministic compositional set-level verifier.

    Stateless. One instance handles many runs. No configuration
    knobs; the 10-rule table is fixed. Tuning is a code change.
    """

    def verify(
        self,
        coverage: ClaimCoverageAnalysis,
        *,
        findings: Iterable[ConflictFinding] = (),
        path_bundle: Sequence | None = None,
    ) -> EvidenceVerificationResult:
        """Apply the 10-rule table and return an EvidenceVerificationResult.

        ``findings``     iterable of ConflictFinding (typically from
                         ConflictDetectionAgent.detect). Empty =
                         no conflict.

        ``path_bundle``  optional tuple of GraphPath from the KG
                         reasoner. Passing ``None`` means "no
                         pathway signal"; passing ``()`` means
                         "I asked, and got nothing", which is a
                         different — and meaningful — signal (V6).
        """

        findings_tuple = tuple(findings)
        hard_findings = [f for f in findings_tuple if f.severity is ConflictSeverity.HARD]
        soft_findings = [f for f in findings_tuple if f.severity is ConflictSeverity.SOFT]

        pathway_bundle_supplied = path_bundle is not None
        pathway_count = len(path_bundle) if pathway_bundle_supplied else 0
        pathway_complete = pathway_bundle_supplied and pathway_count > 0

        evidence_refs = self._gather_refs(coverage, findings_tuple, path_bundle)

        verdict, rule_id, rationale = self._apply_rules(
            coverage=coverage,
            hard_findings=hard_findings,
            soft_findings=soft_findings,
            pathway_bundle_supplied=pathway_bundle_supplied,
            pathway_count=pathway_count,
        )

        return EvidenceVerificationResult(
            verdict=verdict,
            rule_id=rule_id,
            rationale=rationale,
            coverage=coverage,
            findings=findings_tuple,
            pathway_complete=pathway_complete,
            pathway_count=pathway_count,
            evidence_refs=evidence_refs,
            correlation_id=coverage.correlation_id,
        )

    # ------------------------------------------------------------------
    # Rule table
    # ------------------------------------------------------------------

    def _apply_rules(
        self,
        *,
        coverage: ClaimCoverageAnalysis,
        hard_findings: list[ConflictFinding],
        soft_findings: list[ConflictFinding],
        pathway_bundle_supplied: bool,
        pathway_count: int,
    ) -> tuple[EvidenceVerdict, str, str]:
        states = coverage.facet_states

        # V1 — REFUTED: hard recommendation clash with named invertor.
        refuting = self._find_refuting_clash(hard_findings)
        if refuting is not None:
            return (
                EvidenceVerdict.REFUTED,
                "V1",
                f"V1: named invertor in recommendation clash — {refuting.reason}",
            )

        # V2 — CONFLICTING: remaining hard conflicts.
        if hard_findings:
            reasons = "; ".join(f.reason for f in hard_findings)
            return (
                EvidenceVerdict.CONFLICTING,
                "V2",
                f"V2: {len(hard_findings)} hard conflict(s) — {reasons}",
            )

        # V3 — INSUFFICIENT: phenotype missing.
        if states[ClaimEvidenceFacet.PHENOTYPE] is FacetCoverageState.MISSING:
            return (
                EvidenceVerdict.INSUFFICIENT,
                "V3",
                "V3: phenotype evidence missing",
            )

        # V4 — INSUFFICIENT: recommendation missing.
        if states[ClaimEvidenceFacet.RECOMMENDATION] is FacetCoverageState.MISSING:
            return (
                EvidenceVerdict.INSUFFICIENT,
                "V4",
                "V4: recommendation evidence missing",
            )

        # V5 — INSUFFICIENT: any other MISSING facet.
        other_missing = [
            f
            for f in coverage.missing_facets
            if f
            not in {
                ClaimEvidenceFacet.PHENOTYPE,
                ClaimEvidenceFacet.RECOMMENDATION,
            }
        ]
        if other_missing:
            names = ", ".join(f.value for f in other_missing)
            return (
                EvidenceVerdict.INSUFFICIENT,
                "V5",
                f"V5: missing facets — {names}",
            )

        # V6 — UNCERTAIN: caller asked for pathway but bundle is empty.
        if pathway_bundle_supplied and pathway_count == 0:
            return (
                EvidenceVerdict.UNCERTAIN,
                "V6",
                "V6: KG path bundle supplied but empty — pathway unsupported",
            )

        # V7 — UNCERTAIN: POPULATION uncertain.
        if states[ClaimEvidenceFacet.POPULATION] is FacetCoverageState.UNCERTAIN:
            return (
                EvidenceVerdict.UNCERTAIN,
                "V7",
                f"V7: {coverage.population.value} population support weak",
            )

        # V8 — UNCERTAIN: any other UNCERTAIN facet (excluding CONFLICT_FREE,
        # which V9 handles separately so the rationale names the soft conflict).
        other_uncertain = [
            f
            for f in coverage.uncertain_facets
            if f
            not in {
                ClaimEvidenceFacet.POPULATION,
                ClaimEvidenceFacet.CONFLICT_FREE,
            }
        ]
        if other_uncertain:
            names = ", ".join(f.value for f in other_uncertain)
            return (
                EvidenceVerdict.UNCERTAIN,
                "V8",
                f"V8: uncertain facets — {names}",
            )

        # V9 — UNCERTAIN: CONFLICT_FREE uncertain (soft conflict present).
        if states[ClaimEvidenceFacet.CONFLICT_FREE] is FacetCoverageState.UNCERTAIN:
            reasons = "; ".join(f.reason for f in soft_findings) or "soft conflict"
            return (
                EvidenceVerdict.UNCERTAIN,
                "V9",
                f"V9: soft conflict — {reasons}",
            )

        # V10 — SUPPORTED.
        suffix = (
            f"; {pathway_count} KG path(s)"
            if pathway_bundle_supplied
            else "; no KG path bundle supplied"
        )
        return (
            EvidenceVerdict.SUPPORTED,
            "V10",
            f"V10: all facets covered, no hard conflict{suffix}",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_refuting_clash(
        hard_findings: list[ConflictFinding],
    ) -> ConflictFinding | None:
        """Return a RECOMMENDATION_CLASH whose actions include a named
        invertor (AVOID/CONTRAINDICATED vs USE), or None.

        Re-parses the finding's reason string (produced by the
        conflict agent in the format ``"drug for gene/phenotype:
        X vs Y"``) to identify the action pair. Deterministic —
        depends only on the reason string + closed-enum action
        families.
        """

        for f in hard_findings:
            if f.kind is not ConflictKind.RECOMMENDATION_CLASH:
                continue
            reason = f.reason
            # Extract the action-family substrings after the colon.
            # The conflict agent formats as:
            #   "<drug> for <gene>/<phen>: <action_a> vs <action_b>"
            if ":" not in reason:
                continue
            tail = reason.split(":", 1)[1].strip()
            parts = [p.strip() for p in tail.split(" vs ")]
            if len(parts) != 2:
                continue
            # Append a trailing space so bare tokens like "use" match
            # the action keyword "use " (which carries the space to
            # avoid false positives inside words like "house").
            action_a = classify_action(parts[0] + " ")
            action_b = classify_action(parts[1] + " ")
            actions = {action_a, action_b}
            # Invertor pair: one side is USE, the other is AVOID or CONTRA.
            if RecommendationAction.USE in actions and (
                RecommendationAction.AVOID in actions
                or RecommendationAction.CONTRAINDICATED in actions
            ):
                return f
        return None

    @staticmethod
    def _gather_refs(
        coverage: ClaimCoverageAnalysis,
        findings: tuple[ConflictFinding, ...],
        path_bundle: Sequence | None,
    ) -> tuple[str, ...]:
        """Deduplicated, stable-ordered union of evidence refs."""

        refs: list[str] = []
        for facet_refs in coverage.facet_evidence_refs.values():
            refs.extend(facet_refs)
        for f in findings:
            refs.extend(f.source_ids)
        if path_bundle is not None:
            for p in path_bundle:
                evidence_refs = getattr(p, "evidence_refs", ())
                refs.extend(evidence_refs)
        # Dedup preserving first-occurrence order.
        seen: set[str] = set()
        deduped: list[str] = []
        for r in refs:
            if not r or r in seen:
                continue
            seen.add(r)
            deduped.append(r)
        return tuple(deduped)


__all__ = ["SetLevelEvidenceVerifier"]
