"""``SufficiencyCheckpoint`` — orchestrator-facing composition façade.

Phase 6, commit 17 of the Evidence Sufficiency Layer brief. Closes
requirement #21 (integration into orchestration + verification +
MCP memory + execution tracing + provenance).

One class, one public method. Gathers:

    ContextSufficiencyAgent         (phase 1) — coverage + conflict +
                                    provenance + decision
    SetLevelEvidenceVerifier        (phase 4) — 5-verdict rollup
    UncertaintyScoringEngine        (phase 5) — 4-tier uncertainty
    PopulationEvidenceBiasDetector  (phase 5) — 3 bias kinds
    EvidenceSufficiencyTrace        (phase 6 commit 16) — audit record

and runs them in a fixed order, returning a single
``CheckpointResult`` that tells the orchestrator whether synthesis
may proceed.

Scope firewall
--------------
* The checkpoint performs no retrieval, no graph reasoning, no
  document opening, and no LLM calls. It reads already-produced
  pipeline outputs and applies the deterministic rule stack.
* Inputs are restricted to the pharmacogenomic tuple via the
  underlying components' closed-enum signatures.
* Every boundary uses the four brief-named closed enums:
  SufficiencyDecision / EvidenceVerdict / UncertaintyScore /
  BiasKind.

Off by default
--------------
Nothing in the orchestrator uses this class unless
``ExecutionCoordinator.sufficiency_checkpoint`` is explicitly set.
Flagship demo signatures are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

from core.evidence_sufficiency.sufficiency.context_agent import (
    ContextSufficiencyAgent,
)
from core.evidence_sufficiency.sufficiency.decision_engine import (
    SufficiencyDecision,
    SufficiencyReport,
)
from core.evidence_sufficiency.trace import EvidenceSufficiencyTrace
from core.evidence_sufficiency.uncertainty.bias_detector import (
    BiasFinding,
    PopulationEvidenceBiasDetector,
)
from core.evidence_sufficiency.uncertainty.engine import (
    UncertaintyReading,
    UncertaintyScoringEngine,
)
from core.evidence_sufficiency.verifier.result import (
    EvidenceVerdict,
    EvidenceVerificationResult,
)
from core.evidence_sufficiency.verifier.set_level import (
    SetLevelEvidenceVerifier,
)

# ---------------------------------------------------------------------------
# Result record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckpointResult:
    """Frozen bundle returned by ``SufficiencyCheckpoint.evaluate``.

    Fields
    ------
    report          the SufficiencyReport (phase-1 decision engine)
    verdict         the set-level EvidenceVerificationResult (phase 4)
    uncertainty     the UncertaintyReading (phase 5)
    bias_findings   tuple of BiasFindings (phase 5)
    trace           fully-populated EvidenceSufficiencyTrace
    allows_synthesis final answer the orchestrator checks — True iff
                    none of the four layers want to block
    blocking_reason empty when allows_synthesis=True; otherwise a
                    one-line string naming which layer blocked and
                    why. Used by the orchestrator's escalation path.
    """

    report: SufficiencyReport
    verdict: EvidenceVerificationResult
    uncertainty: UncertaintyReading
    bias_findings: tuple[BiasFinding, ...]
    trace: EvidenceSufficiencyTrace
    allows_synthesis: bool
    blocking_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "allows_synthesis": self.allows_synthesis,
            "blocking_reason": self.blocking_reason,
            "sufficiency_decision": self.report.decision.value,
            "sufficiency_rationale": self.report.rationale,
            "verdict": self.verdict.verdict.value,
            "verdict_rule_id": self.verdict.rule_id,
            "uncertainty_score": self.uncertainty.score.value,
            "uncertainty_action": self.uncertainty.action.value,
            "bias_findings": [b.to_dict() for b in self.bias_findings],
            "trace": self.trace.to_dict(),
            # Coverage signals flattened for frontend convenience — the
            # full ClaimCoverageAnalysis lives in the checkpoint's
            # SufficiencyReport, but dashboards want the top-level view.
            "coverage_ratio": self.report.coverage.coverage_ratio,
            "missing_facets": [f.value for f in self.report.coverage.missing_facets],
            "uncertain_facets": [f.value for f in self.report.coverage.uncertain_facets],
        }


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------


@dataclass
class SufficiencyCheckpoint:
    """Orchestration-facing façade composing the full sufficiency stack.

    Stateless. Injectable components default to their canonical
    implementations so the simplest call site is zero-arg:

        checkpoint = SufficiencyCheckpoint()
        result = checkpoint.evaluate(run, retrieval_docs=..., ...)
    """

    context_agent: ContextSufficiencyAgent = field(default_factory=ContextSufficiencyAgent)
    set_level_verifier: SetLevelEvidenceVerifier = field(default_factory=SetLevelEvidenceVerifier)
    uncertainty_engine: UncertaintyScoringEngine = field(default_factory=UncertaintyScoringEngine)
    bias_detector: PopulationEvidenceBiasDetector = field(
        default_factory=PopulationEvidenceBiasDetector
    )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        run: dict[str, Any],
        *,
        retrieval_docs: Iterable[Any] | None = None,
        provenance_records: Iterable[Any] | None = None,
        conflict_claims: Iterable[dict[str, Any]] | None = None,
        path_bundle: Sequence | None = None,
        pop_indexer: Any = None,
        retrieval_rounds: Iterable[dict[str, Any]] | None = None,
        correlation_id: str = "",
    ) -> CheckpointResult:
        """Run the full sufficiency stack and return a CheckpointResult.

        Order of operations (deterministic, documented):

          1. ContextSufficiencyAgent.evaluate
                -> SufficiencyReport (decision + coverage + findings)
          2. SetLevelEvidenceVerifier.verify
                -> EvidenceVerificationResult (5-verdict rollup)
          3. UncertaintyScoringEngine.score
                -> UncertaintyReading (4-tier + action)
          4. PopulationEvidenceBiasDetector.detect
                -> tuple[BiasFinding]
          5. Assemble EvidenceSufficiencyTrace from all of the above
          6. Compute allows_synthesis + blocking_reason

        The orchestrator may skip synthesis when ``allows_synthesis``
        is False and record ``blocking_reason`` on the escalation
        path — exactly the same pattern as the existing conflict
        resolver + verification gate.
        """

        # 1. Sufficiency report
        report = self.context_agent.evaluate(
            run,
            retrieval_docs=retrieval_docs,
            provenance_records=provenance_records,
            conflict_claims=conflict_claims,
            correlation_id=correlation_id,
        )

        # 2. Set-level verdict (reads the coverage + findings the
        # sufficiency agent already produced — single source of truth).
        verdict = self.set_level_verifier.verify(
            report.coverage,
            findings=report.findings,
            path_bundle=path_bundle,
        )

        # 3. Uncertainty score.
        uncertainty = self.uncertainty_engine.score(
            report.coverage,
            findings=report.findings,
            path_bundle=path_bundle,
        )

        # 4. Bias findings.
        bias_findings = self.bias_detector.detect(
            report.coverage,
            pop_indexer=pop_indexer,
        )

        # 5. Trace assembly.
        trace = self._assemble_trace(
            correlation_id=correlation_id,
            report=report,
            verdict=verdict,
            uncertainty=uncertainty,
            path_bundle=path_bundle,
            retrieval_rounds=retrieval_rounds,
        )

        # 6. Final synthesis gate + blocking reason.
        allows, reason = self._synthesis_gate(report, verdict, uncertainty)

        return CheckpointResult(
            report=report,
            verdict=verdict,
            uncertainty=uncertainty,
            bias_findings=bias_findings,
            trace=trace,
            allows_synthesis=allows,
            blocking_reason=reason,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _assemble_trace(
        *,
        correlation_id: str,
        report: SufficiencyReport,
        verdict: EvidenceVerificationResult,
        uncertainty: UncertaintyReading,
        path_bundle: Sequence | None,
        retrieval_rounds: Iterable[dict[str, Any]] | None,
    ) -> EvidenceSufficiencyTrace:
        """Build the EvidenceSufficiencyTrace from already-computed signals."""

        t = EvidenceSufficiencyTrace.empty(correlation_id=correlation_id)

        # Evidence refs — union of coverage + verdict (both already deduplicated
        # internally; the trace's record_evidence dedupes further).
        t = t.record_evidence(verdict.evidence_refs)

        # Graph paths — serialize if a bundle was supplied; empty list if not.
        if path_bundle is not None:
            serialized: list[dict[str, Any]] = []
            for p in path_bundle:
                to_dict = getattr(p, "to_dict", None)
                if callable(to_dict):
                    serialized.append(to_dict())
            if serialized:
                t = t.record_graph_paths(tuple(serialized))

        # Missing hops — snapshot of facets in MISSING or UNCERTAIN.
        hops = [f.value for f in report.coverage.missing_facets]
        hops.extend(f.value for f in report.coverage.uncertain_facets)
        t = t.record_missing_hops(tuple(hops))

        # Uncertainty transition — one entry per evaluate() call.
        t = t.record_uncertainty(uncertainty.score.value)

        # Sufficiency decision.
        t = t.record_sufficiency_decision(report.decision.value)

        # Retrieval-loop summaries (caller provides; optional).
        if retrieval_rounds:
            for entry in retrieval_rounds:
                t = t.record_retrieval_loop(
                    round_index=int(entry.get("round_index", 0)),
                    strategies=tuple(entry.get("strategies", ())),
                    stop_signal=str(entry.get("stop_signal", "")),
                )

        # Escalation events derived from the decision/verdict/uncertainty.
        # Closed-enum mapping; extending is a code change.
        escalations: list[str] = []
        if report.decision is SufficiencyDecision.BLOCK:
            escalations.append("BLOCK_SYNTHESIS")
        if report.decision is SufficiencyDecision.ABSTAIN:
            escalations.append("ABSTAIN")
        if report.decision is SufficiencyDecision.ESCALATE:
            escalations.append("ROUTE_TO_HUMAN_REVIEW")
        if report.decision is SufficiencyDecision.REQUEST_MORE:
            escalations.append("REQUEST_ADDITIONAL_EVIDENCE")
        if verdict.verdict is EvidenceVerdict.REFUTED:
            escalations.append("VERDICT_REFUTED")
        for action in escalations:
            t = t.record_escalation(action)

        return t

    @staticmethod
    def _synthesis_gate(
        report: SufficiencyReport,
        verdict: EvidenceVerificationResult,
        uncertainty: UncertaintyReading,
    ) -> tuple[bool, str]:
        """Decide whether synthesis may run.

        Any of the three layers can block. First blocker named wins
        in the reason string so the audit trail points at the
        specific layer:

          1. sufficiency report says is_blocking
          2. verdict is not SUPPORTED
          3. uncertainty action is BLOCK (UNSAFE tier)

        Otherwise -> allow synthesis. MODERATE uncertainty still
        allows synthesis; the caller can caveat the output via the
        ``uncertainty`` field on the CheckpointResult.
        """

        if report.is_blocking:
            return (
                False,
                f"sufficiency:{report.decision.value}:{report.rationale}",
            )
        if not verdict.allows_synthesis:
            return (
                False,
                f"verdict:{verdict.verdict.value}:{verdict.rationale}",
            )
        from core.evidence_sufficiency.uncertainty.engine import (
            UncertaintyAction,
        )

        if uncertainty.action is UncertaintyAction.BLOCK:
            return (
                False,
                f"uncertainty:{uncertainty.score.value}:{uncertainty.rationale}",
            )
        return True, ""


__all__ = [
    "CheckpointResult",
    "SufficiencyCheckpoint",
]
