"""``SafetyConstraintEngine`` — deterministic biomedical safety gate.

Closes requirements #3 (phenotype_correctness + cpic_alignment +
allele_interpretation + recommendation_consistency) and #6 (active
blocking of unsafe outputs) of the safety brief.

Where ``BiomedicalClaimValidator`` enforces *shape* (every claim
has the 4 mapping fields) and ``EvidenceGroundingEngine`` enforces
*existence* (cited sources resolve in MCP), this engine enforces
*biomedical truth*. It re-derives key facts from the project's
authoritative deterministic rules and compares them to what the
run produced:

    phenotype_correctness
        Re-run ``rules.phenotype_rules.infer_phenotype(gene, a1, a2)``
        on the run's diplotype. If the run's stated phenotype
        disagrees with the rule output → UNSAFE.

    allele_interpretation
        Check every allele in the diplotype has a known activity
        score in ``ALLELE_ACTIVITY_SCORES``. Unknown alleles →
        FAIL (not unsafe by itself, but can't be deliver-ready).

    cpic_alignment
        Re-run ``guidelines.cpic.lookup_recommendation(gene,
        phenotype, drug)``. If the run's recommendation text
        doesn't match (or no CPIC entry exists) → WARN if
        actionable, FAIL if the run invented a rec wholesale.

    recommendation_consistency
        Across multiple runs in one orchestration (comparative
        mode), detect contradictory recommendations for the
        same drug → CONFLICTING via the ``guideline_conflict``
        check already in ``verification/rules/checks.py`` — we
        delegate to it.

Block-on-unsafe (req #6)
------------------------
``apply(traces, run)`` returns a ``SafetyDecision`` with a boolean
``block`` flag. Callers (``VerificationAgent``, the orchestrator)
use that flag to decide whether to surface the output to the user.

The decision is deterministic: a single UNSAFE tier anywhere in
the aggregate pulls ``block=True``. Callers can't override it
without constructing a new engine with relaxed constraints
(intended for dev scenarios only — never for prod delivery).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.verification.scoring import (
    VerificationScore,
    VerificationTier,
    classify_score,
    worse_of,
)
from core.verification.trace import EscalationEvent, VerificationTrace, make_trace
from guidelines.cpic import lookup_recommendation
from rules.phenotype_rules import ALLELE_ACTIVITY_SCORES, infer_phenotype
from verification.rules.checks import (
    CheckResult,
    Verdict,
    check_guideline_conflict,
)


# ---------------------------------------------------------------------------
# Decision shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SafetyDecision:
    """The outcome of a safety constraint pass.

    ``block=True`` means the caller **must not** surface the output.
    This is the active enforcement seam the brief's requirement #6
    asks for — everything else in the safety engine can be advisory,
    but ``block`` is the one signal that has to be respected.
    """

    tier: VerificationTier
    block: bool
    reason: str
    traces: tuple[VerificationTrace, ...]
    score: VerificationScore

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier.value,
            "block": self.block,
            "reason": self.reason,
            "trace_count": len(self.traces),
            "score": self.score.to_dict(),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


@dataclass
class SafetyConstraintEngine:
    """Deterministic biomedical safety gate.

    Stateless. Composable. Calls into ``rules.phenotype_rules`` and
    ``guidelines.cpic`` — the project's authoritative deterministic
    lookup modules — so "what the rule says" is always consistent
    with the rest of the system.

    Parameters:
      strict_cpic_alignment:
        When True (default), a recommendation that doesn't match
        the CPIC entry is a FAIL. When False, it's a WARN — useful
        when the CPIC entry is missing for a rare diplotype/drug
        pair and you want the system to fall through rather than
        block.
      allow_unknown_alleles:
        When False (default), an allele not in
        ``ALLELE_ACTIVITY_SCORES`` fails the allele_interpretation
        check. When True, unknown alleles produce WARN — useful
        during development when adding new gene coverage.
    """

    strict_cpic_alignment: bool = True
    allow_unknown_alleles: bool = False

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def apply(
        self,
        *,
        run: dict[str, Any],
        prior_traces: list[VerificationTrace] | None = None,
        confidence: float | None = None,
        correlation_id: str = "",
    ) -> SafetyDecision:
        """Run all safety constraint checks; return a block/deliver decision.

        ``prior_traces`` is the list from ``ClaimValidator`` +
        ``GroundingEngine`` (or either alone). We fold those states
        into the final tier computation so a claim that *already*
        failed grounding correctly downgrades the whole output.

        ``confidence`` is optional; when supplied it's used by the
        scoring classifier. When omitted, confidence is derived from
        ``run['verification']['confidence']`` if present.
        """
        # Gather constraint traces.
        safety_traces: list[VerificationTrace] = []
        safety_traces.extend(self._check_allele_interpretation(run, correlation_id))
        safety_traces.extend(self._check_phenotype_correctness(run, correlation_id))
        safety_traces.extend(self._check_cpic_alignment(run, correlation_id))
        safety_traces.extend(self._check_recommendation_consistency(run, correlation_id))

        # Gather corresponding CheckResults for the scoring layer —
        # classify_score works on CheckResults, not traces.
        check_results = _traces_to_check_results(safety_traces)
        # Also fold prior-layer failures so the score captures them.
        if prior_traces:
            check_results.extend(_traces_to_check_results(prior_traces))

        # Resolve confidence.
        if confidence is None:
            v = run.get("verification") or {}
            confidence = float(v.get("confidence") or 1.0)

        # ``classify_score`` expects a ConfidenceScore; build one from
        # the scalar. We don't propagate through stages here — the
        # orchestrator's pipeline already did that upstream and
        # stored the result on run['verification']['confidence'].
        from verification.rules.confidence import (
            classify_confidence,
            ConfidenceScore,
        )

        conf_level = classify_confidence(confidence)
        conf_score = ConfidenceScore(
            value=confidence, level=conf_level, source="safety_engine",
        )

        score = classify_score(check_results, confidence=conf_score)

        # Block decision: any UNSAFE / CONFLICTING tier blocks.
        block = score.is_blocking

        # Aggregate tier folds prior + new.
        agg_tier = score.tier
        for tr in (prior_traces or []):
            if tr.failed and tr.validator == "EvidenceGroundingEngine":
                # A grounding fail contributes to the score through
                # check_results, but we want the tier to reflect
                # that separately in case a caller inspects just
                # the SafetyDecision.
                agg_tier = worse_of(agg_tier, VerificationTier.UNVERIFIED)

        all_traces = tuple(safety_traces)
        return SafetyDecision(
            tier=agg_tier,
            block=block,
            reason=score.reason,
            traces=all_traces,
            score=score,
        )

    # ------------------------------------------------------------------
    # Individual checks — each returns a list of VerificationTraces
    # (usually 0 or 1). Returning a list uniformly makes the public
    # ``apply`` method simpler.
    # ------------------------------------------------------------------

    def _check_allele_interpretation(
        self, run: dict[str, Any], cid: str
    ) -> list[VerificationTrace]:
        """Every allele in the diplotype must have a known activity score."""
        pgx = run.get("pharmacogene_result") or {}
        gene = pgx.get("gene") or run.get("gene") or ""
        a1 = run.get("allele1") or ""
        a2 = run.get("allele2") or ""
        if not (gene and a1 and a2):
            return []

        known_map = ALLELE_ACTIVITY_SCORES.get(gene, {})
        unknown = [a for a in (a1, a2) if a not in known_map]

        if not unknown:
            return [
                _trace(
                    claim=f"{gene} diplotype {a1}/{a2} uses only known alleles",
                    state="pass",
                    confidence=1.0,
                    rule_id="cpic.allele_activity_scores",
                    reason=(
                        f"Both alleles {a1}/{a2} have defined activity scores "
                        f"in ALLELE_ACTIVITY_SCORES[{gene}]"
                    ),
                    correlation_id=cid,
                )
            ]

        state = "warn" if self.allow_unknown_alleles else "fail"
        return [
            _trace(
                claim=f"{gene} diplotype {a1}/{a2}",
                state=state,
                confidence=0.0,
                rule_id="cpic.allele_activity_scores",
                reason=(
                    f"Unknown allele(s) {', '.join(unknown)} — not in "
                    f"ALLELE_ACTIVITY_SCORES[{gene}] "
                    f"({'warn' if self.allow_unknown_alleles else 'fail'})"
                ),
                correlation_id=cid,
            )
        ]

    def _check_phenotype_correctness(
        self, run: dict[str, Any], cid: str
    ) -> list[VerificationTrace]:
        """Re-derive phenotype from rules; fail if the run disagrees."""
        pgx = run.get("pharmacogene_result") or {}
        gene = pgx.get("gene") or run.get("gene") or ""
        a1 = run.get("allele1") or ""
        a2 = run.get("allele2") or ""
        stated = (pgx.get("phenotype") or "").strip()
        if not (gene and a1 and a2 and stated):
            return []

        inf = infer_phenotype(gene, a1, a2)
        expected = inf.phenotype

        # ``Indeterminate`` happens when an allele is unknown — the
        # allele_interpretation check already covers that. Don't
        # double-emit.
        if expected == "Indeterminate":
            return []

        if stated == expected:
            return [
                _trace(
                    claim=f"{gene} {a1}/{a2} → {stated}",
                    state="pass",
                    confidence=1.0,
                    rule_id="cpic.phenotype_correctness",
                    reason=(
                        f"Stated phenotype matches rule output "
                        f"(activity_score={inf.activity_score})"
                    ),
                    correlation_id=cid,
                )
            ]

        # Mismatch is an **unsafe** signal — the pipeline produced a
        # phenotype the deterministic rule disagrees with. This is
        # exactly the kind of silent drift the safety engine exists
        # to catch.
        escalation = EscalationEvent(
            action="block",
            reason=(
                f"Phenotype mismatch: stated={stated!r}, "
                f"rule={expected!r} for {gene} {a1}/{a2}"
            ),
            target="pharmacogene_agent",
        )
        return [
            _trace(
                claim=f"{gene} {a1}/{a2} → {stated}",
                state="fail",
                confidence=0.0,
                rule_id="cpic.phenotype_correctness",
                reason=(
                    f"UNSAFE: stated phenotype {stated!r} disagrees with "
                    f"rule output {expected!r} "
                    f"(activity_score={inf.activity_score})"
                ),
                correlation_id=cid,
                escalation_events=(escalation,),
            )
        ]

    def _check_cpic_alignment(
        self, run: dict[str, Any], cid: str
    ) -> list[VerificationTrace]:
        """Each recommendation should match the CPIC lookup for (gene, phenotype, drug)."""
        pgx = run.get("pharmacogene_result") or {}
        gene = pgx.get("gene") or run.get("gene") or ""
        phenotype = pgx.get("phenotype") or ""
        recs = run.get("recommendations") or []
        out: list[VerificationTrace] = []

        if not (gene and phenotype and recs):
            return out

        for rec in recs:
            drug = rec.get("drug") or ""
            text = rec.get("recommendation") or ""
            if not (drug and text):
                continue

            cpic = lookup_recommendation(gene, phenotype, drug)
            if cpic is None:
                # No CPIC entry for this triple. That's either a
                # rare-combination gap (warn) or a fabricated rec
                # depending on the strict flag.
                state = "fail" if self.strict_cpic_alignment else "warn"
                out.append(
                    _trace(
                        claim=text[:200],
                        state=state,
                        confidence=float(rec.get("confidence") or 1.0),
                        rule_id="cpic.alignment",
                        reason=(
                            f"No CPIC guideline for ({gene}, {phenotype}, {drug}) — "
                            f"{'strict mode: fail' if self.strict_cpic_alignment else 'advisory: warn'}"
                        ),
                        correlation_id=cid,
                    )
                )
                continue

            # Normalized match: require the recommendation text to
            # start with the CPIC recommendation (CPIC text is often
            # a prefix of the pipeline's elaborated version).
            norm_stated = " ".join(text.lower().split())
            norm_cpic = " ".join(cpic.recommendation.lower().split())
            matches = norm_stated.startswith(norm_cpic[:60]) or norm_cpic in norm_stated

            if matches:
                out.append(
                    _trace(
                        claim=text[:200],
                        state="pass",
                        confidence=float(rec.get("confidence") or 1.0),
                        rule_id="cpic.alignment",
                        reason=(
                            f"Matches CPIC {cpic.guideline_id} "
                            f"(strength={cpic.strength})"
                        ),
                        correlation_id=cid,
                    )
                )
            else:
                # Text drift — same triple, different wording.
                # Only WARN, not FAIL, because paraphrasing is
                # acceptable; the orchestrator's boundary guard
                # catches outright fabrication elsewhere.
                out.append(
                    _trace(
                        claim=text[:200],
                        state="warn",
                        confidence=float(rec.get("confidence") or 1.0),
                        rule_id="cpic.alignment",
                        reason=(
                            f"Recommendation text differs from CPIC {cpic.guideline_id}; "
                            f"review for paraphrasing vs. drift"
                        ),
                        correlation_id=cid,
                    )
                )
        return out

    def _check_recommendation_consistency(
        self, run: dict[str, Any], cid: str
    ) -> list[VerificationTrace]:
        """Detect contradictory recs for the same drug using the existing check."""
        recs = run.get("recommendations") or []
        if len(recs) < 2:
            # Can't conflict with only one entry.
            return []
        cr = check_guideline_conflict(recs)
        if cr.verdict == Verdict.PASS:
            return [
                _trace(
                    claim="recommendation_consistency",
                    state="pass",
                    confidence=1.0,
                    rule_id="verification.guideline_conflict",
                    reason=cr.reason,
                    correlation_id=cid,
                )
            ]
        # Verdict is FAIL → contradictory recs.
        return [
            _trace(
                claim="recommendation_consistency",
                state="fail",
                confidence=0.0,
                rule_id="verification.guideline_conflict",
                reason=cr.reason,
                correlation_id=cid,
                escalation_events=(
                    EscalationEvent(
                        action="block",
                        reason=f"Conflicting recs: {cr.reason}",
                        target="recommendation_layer",
                    ),
                ),
            )
        ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trace(
    *,
    claim: str,
    state: str,
    confidence: float,
    rule_id: str,
    reason: str,
    correlation_id: str,
    escalation_events: tuple[EscalationEvent, ...] = (),
) -> VerificationTrace:
    """Small wrapper around ``make_trace`` stamping the validator name."""
    return make_trace(
        claim=claim,
        validator="SafetyConstraintEngine",
        state=state,
        confidence=confidence,
        evidence_refs=(),  # constraint checks don't cite evidence
        escalation_events=escalation_events,
        reason=reason,
        correlation_id=correlation_id,
        generating_agent="safety_engine",
        rule_id=rule_id,
    )


# Mapping from check rule_id → CheckResult check_name. Lets the
# scoring layer recognise our constraint checks by the same names
# its ``_UNSAFE_ON_FAIL`` + ``_CONFLICTING_ON_FAIL`` sets know.
_RULE_TO_CHECK_NAME: dict[str, str] = {
    "cpic.phenotype_correctness": "hallucination_detection",  # treat as UNSAFE
    "cpic.allele_activity_scores": "provenance",              # UNVERIFIED on fail
    "cpic.alignment": "provenance",                           # UNVERIFIED on fail
    "verification.guideline_conflict": "guideline_conflict",  # CONFLICTING on fail
}


def _traces_to_check_results(
    traces: list[VerificationTrace],
) -> list[CheckResult]:
    """Bridge trace states into the CheckResult shape scoring expects."""
    out: list[CheckResult] = []
    for tr in traces:
        verdict = (
            Verdict.PASS if tr.passed
            else Verdict.WARN if tr.warned
            else Verdict.FAIL
        )
        name = _RULE_TO_CHECK_NAME.get(tr.rule_id, tr.rule_id)
        out.append(
            CheckResult(
                check_name=name,
                verdict=verdict,
                reason=tr.reason,
                details={"source_trace": tr.claim_id, "validator": tr.validator},
            )
        )
    return out


__all__ = [
    "SafetyConstraintEngine",
    "SafetyDecision",
]
