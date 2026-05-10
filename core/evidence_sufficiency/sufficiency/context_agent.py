"""``ContextSufficiencyAgent`` — orchestration-facing sufficiency façade.

Phase 1 of the Evidence Sufficiency Layer brief, final piece.

Thin composition layer: gathers inputs the orchestrator already has
(a run dict, retrieval docs, optional provenance records, optional
claim bundle for conflict detection), drives the three deterministic
analyzers in the right order, and returns a single
``SufficiencyReport``.

Contract
--------

``evaluate(run, *, retrieval_docs=None, provenance_records=None,
conflict_claims=None, correlation_id="") -> SufficiencyReport``

Inputs
  run                   orchestrator run dict (same shape as
                        ``BiomedicalClaimValidator.validate_run``
                        and ``EvidenceCoverageAnalyzer.analyze``)
  retrieval_docs        iterable of ``BiomedicalDocument``
                        (or dict-shaped equivalents); passed through
                        to ``EvidenceCoverageAnalyzer``
  provenance_records    iterable of ``ProvenanceRecord``-shaped items
                        (when omitted the engine skips R4; attribution
                        isn't audited but the other rules still fire)
  conflict_claims       iterable of typed claim dicts for the
                        conflict detector (see
                        ``ConflictDetectionAgent`` docstring for
                        the shape); when omitted the detector
                        receives an empty iterable and CONFLICT_FREE
                        stays optimistic
  correlation_id        propagated into the resulting report for
                        MCP linkage

Execution order (deterministic)
  1. EvidenceCoverageAnalyzer.analyze → base ClaimCoverageAnalysis
  2. ConflictDetectionAgent.detect     → tuple of findings
  3. ConflictDetectionAgent.apply_to   → downgrades CONFLICT_FREE
  4. ProvenanceCoverageTracker.audit   → optional provenance report
  5. SufficiencyDecisionEngine.decide  → final SufficiencyReport

The agent itself performs no reasoning. Every behaviour is in the
analyzers + engine. Responsibilities are contained so swapping any
one component (e.g. a graph-aware conflict detector in phase 3) is
a component swap, not an agent rewrite.

Scope firewall
--------------
This is not an orchestrator. It does not run the swarm, dispatch
messages, or call the generative layer. It answers exactly one
question — "is the evidence sufficient for this run?" — and hands
back a decision the real orchestrator honours. The orchestrator
integration point lives in phase 6 (``sufficiency_enabled`` flag on
the coordinator). Until then, this wrapper is callable directly by
demos and tests.

Off by default in production. The orchestrator does not instantiate
it unless ``sufficiency_enabled=True`` — existing flagship demo
signatures are preserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

from core.evidence_sufficiency.conflict.agent import (
    ConflictDetectionAgent,
    ConflictFinding,
)
from core.evidence_sufficiency.coverage.analyzer import EvidenceCoverageAnalyzer
from core.evidence_sufficiency.coverage.provenance_tracker import (
    ProvenanceCoverageTracker,
)
from core.evidence_sufficiency.sufficiency.decision_engine import (
    SufficiencyDecisionEngine,
    SufficiencyReport,
)


@dataclass
class ContextSufficiencyAgent:
    """Deterministic orchestration-facing sufficiency façade.

    Assembled from three stateless analyzers + one stateless engine.
    The agent itself is stateless too — one instance handles many
    runs. No configuration knobs; behaviour is pinned by the
    component classes. Tuning is a code change at the component
    level, which keeps scope drift visible.
    """

    analyzer: EvidenceCoverageAnalyzer = field(default_factory=EvidenceCoverageAnalyzer)
    conflict_detector: ConflictDetectionAgent = field(default_factory=ConflictDetectionAgent)
    provenance_tracker: ProvenanceCoverageTracker = field(default_factory=ProvenanceCoverageTracker)
    engine: SufficiencyDecisionEngine = field(default_factory=SufficiencyDecisionEngine)

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
        correlation_id: str = "",
    ) -> SufficiencyReport:
        """Run the full sufficiency pipeline and return a report.

        Steps execute in a fixed order (documented on the module).
        Each step is idempotent; re-running the same inputs produces
        the same report.
        """

        # 1. Facet-level coverage
        coverage = self.analyzer.analyze(
            run,
            retrieval_docs=retrieval_docs,
            correlation_id=correlation_id,
        )

        # 2. Conflict detection — only over explicitly-typed claims.
        # If the caller didn't pass any, the detector returns () and
        # CONFLICT_FREE stays at its optimistic default.
        findings: tuple[ConflictFinding, ...] = self.conflict_detector.detect(conflict_claims or ())

        # 3. Downgrade CONFLICT_FREE on the coverage analysis.
        coverage = self.conflict_detector.apply_to(coverage, findings)

        # 4. Optional provenance audit.
        provenance_report = None
        if provenance_records is not None:
            provenance_report = self.provenance_tracker.audit(
                provenance_records, correlation_id=correlation_id
            )

        # 5. Apply the 12-rule decision table.
        return self.engine.decide(
            coverage,
            provenance=provenance_report,
            findings=findings,
        )


__all__ = ["ContextSufficiencyAgent"]
