"""``AdaptiveRetrievalController`` — sufficiency-aware retrieval loop.

Phase 2, commit 8 of the Evidence Sufficiency Layer brief.

Composes the pieces shipped in commits 6-8 into one loop:

    retrievers          N BiomedicalRetriever instances
    selector            EvidenceSelector (diversity + dedup merger)
    sufficiency_agent   ContextSufficiencyAgent (phase 1)
    stopper             RetrievalStoppingController

Loop (pseudocode)
-----------------

    for iteration in 0 .. budget-1:
        results = [r.retrieve(query) for r in active_retrievers]
        merged  = selector.select(results)
        run     = compose_run(query, merged)
        report  = sufficiency_agent.evaluate(run, retrieval_docs=...)
        signal  = stopper.decide(report, iteration, budget=budget)
        if signal == STOP   : return AdaptiveRetrievalOutcome(report, iteration+1, False)
        if signal == ABORT  : return AdaptiveRetrievalOutcome(report, iteration+1, True)
        # FETCH_MORE — broaden retrievers for the next round

Broadening strategy (deterministic)
-----------------------------------

Every round the controller introduces one more retriever from its
ordered ``strategies`` list (if any remain). The order is the
constructor argument; by default it is

    [DenseSemanticRetriever, PopulationAwareRetriever, GraphRetriever]

Round 0 uses one retriever, round 1 uses two, etc. This means the
controller never over-fetches: a sufficient answer at round 0
short-circuits the remaining strategies; REQUEST_MORE at round 0
triggers the population-aware re-ranker; REQUEST_MORE at round 1
triggers the (phase-3) graph retriever. Budget caps the maximum
depth.

Scope firewall
--------------
The loop never forms a new query. Every retriever receives the
same ``BiomedicalQuery`` with the same pharmacogenomic scope. The
selector enforces cross-scope rejection, so even a buggy retriever
returning a mismatched query fails fast inside the loop.

Off by default
--------------
Exactly like ``ContextSufficiencyAgent``, this controller is not
wired into the orchestrator. It is callable directly by
demos/tests; phase 6 wires it behind ``sufficiency_enabled=True``.
Existing demo signatures are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from core.evidence_sufficiency.sufficiency.context_agent import (
    ContextSufficiencyAgent,
)
from core.evidence_sufficiency.sufficiency.decision_engine import (
    SufficiencyDecision,
    SufficiencyReport,
)
from retrieval.multi_strategy.biomedical_retriever import (
    BiomedicalQuery,
    BiomedicalRetriever,
    DenseSemanticRetriever,
    PopulationAwareRetriever,
    RetrievalStrategyResult,
)
from retrieval.multi_strategy.graph_and_selector import (
    EvidenceSelector,
    GraphRetriever,
)
from retrieval.stopping.controller import (
    RetrievalStoppingController,
    StopSignal,
)


# ---------------------------------------------------------------------------
# Final outcome record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdaptiveRetrievalOutcome:
    """Frozen result of an adaptive retrieval loop.

    Fields
    ------
    report              the final SufficiencyReport
    rounds_completed    how many retrieval rounds ran (>= 1)
    budget_exhausted    True iff the stopping controller emitted
                        ABORT (REQUEST_MORE still pending at the
                        last permitted round)
    strategies_used     tuple of strategy names active on the final
                        round, in broadening order
    merged_result       the last RetrievalStrategyResult the
                        selector produced; preserves evidence +
                        citations the sufficiency layer read
    query               the query the loop executed
    created_at          ISO timestamp
    """

    report: SufficiencyReport
    rounds_completed: int
    budget_exhausted: bool
    strategies_used: tuple[str, ...]
    merged_result: RetrievalStrategyResult
    query: BiomedicalQuery
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.report.decision.value,
            "rationale": self.report.rationale,
            "rounds_completed": self.rounds_completed,
            "budget_exhausted": self.budget_exhausted,
            "strategies_used": list(self.strategies_used),
            "total_evidence_retrieved": self.merged_result.total_retrieved,
            "citation_ids": [
                c.citation_id for c in self.merged_result.result.citations
            ],
            "coverage_ratio": self.report.coverage.coverage_ratio,
            "missing_facets": [
                f.value for f in self.report.coverage.missing_facets
            ],
            "uncertain_facets": [
                f.value for f in self.report.coverage.uncertain_facets
            ],
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


@dataclass
class AdaptiveRetrievalController:
    """Sufficiency-aware budgeted retrieval loop.

    Composition, not a new retriever itself. All four dependencies
    are injectable to keep the class testable; defaults reflect
    the phase-2 canonical pipeline.
    """

    # Ordered retrieval strategies. Round N uses strategies[:N+1].
    strategies: Sequence[BiomedicalRetriever] = field(
        default_factory=lambda: (
            DenseSemanticRetriever(),
            PopulationAwareRetriever(),
            GraphRetriever(),
        )
    )
    selector: EvidenceSelector = field(default_factory=EvidenceSelector)
    sufficiency_agent: ContextSufficiencyAgent = field(
        default_factory=ContextSufficiencyAgent
    )
    stopper: RetrievalStoppingController = field(
        default_factory=RetrievalStoppingController
    )
    default_budget: int = 3

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        query: BiomedicalQuery,
        run_factory,
        *,
        retrieval_docs: Iterable[Any] | None = None,
        provenance_records: Iterable[Any] | None = None,
        conflict_claims: Iterable[dict[str, Any]] | None = None,
        budget: int | None = None,
        correlation_id: str = "",
    ) -> AdaptiveRetrievalOutcome:
        """Execute the adaptive loop and return an outcome.

        ``run_factory`` is a callable ``(query, merged_result) -> dict``
        that composes the orchestrator-style run dict the sufficiency
        agent consumes (same shape as BiomedicalClaimValidator). It is
        supplied by the caller because the loop itself does not
        synthesize phenotype/recommendation — those come from the
        deterministic agents the orchestrator has wired. The factory
        keeps sufficiency a policy layer, not a synthesis layer.

        Budget defaults to ``self.default_budget`` and is upper-bounded
        by ``len(self.strategies)`` — round N uses strategies[:N+1], so
        there is no value in asking for more rounds than strategies.

        Determinism: every call with identical arguments produces an
        identical outcome (modulo timestamps and MCP record uuids).
        """

        if not self.strategies:
            raise ValueError(
                "AdaptiveRetrievalController requires at least one strategy"
            )

        effective_budget = min(
            int(budget if budget is not None else self.default_budget),
            len(self.strategies),
        )
        effective_budget = max(effective_budget, 1)

        last_report: SufficiencyReport | None = None
        last_merged: RetrievalStrategyResult | None = None
        strategies_used: tuple[str, ...] = ()
        rounds_completed = 0
        budget_exhausted = False

        for iteration in range(effective_budget):
            rounds_completed = iteration + 1
            active = list(self.strategies[: iteration + 1])
            strategies_used = tuple(s.strategy_name for s in active)

            # 1. Run each active retriever.
            results: list[RetrievalStrategyResult] = [
                s.retrieve(query) for s in active
            ]
            # 2. Merge.
            merged = self.selector.select(results, query=query)
            last_merged = merged

            # 3. Compose a sufficiency-style run dict via the caller's factory.
            run_dict = run_factory(query, merged)

            # 4. Evaluate sufficiency.
            last_report = self.sufficiency_agent.evaluate(
                run_dict,
                retrieval_docs=retrieval_docs,
                provenance_records=provenance_records,
                conflict_claims=conflict_claims,
                correlation_id=correlation_id,
            )

            # 5. Ask the stopper.
            signal = self.stopper.decide(
                last_report, iteration, budget=effective_budget
            )
            if signal is StopSignal.STOP:
                budget_exhausted = False
                break
            if signal is StopSignal.ABORT:
                budget_exhausted = True
                break
            # FETCH_MORE — continue the loop; next iteration adds one strategy.

        # Defensive — the loop always runs at least once because
        # effective_budget >= 1; the asserts below are guaranteed.
        assert last_report is not None
        assert last_merged is not None

        return AdaptiveRetrievalOutcome(
            report=last_report,
            rounds_completed=rounds_completed,
            budget_exhausted=budget_exhausted,
            strategies_used=strategies_used,
            merged_result=last_merged,
            query=query,
        )


__all__ = [
    "AdaptiveRetrievalController",
    "AdaptiveRetrievalOutcome",
]
