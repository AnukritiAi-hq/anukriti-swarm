"""``BiomedicalRetriever`` — strategy interface + base types.

Phase 2 of the Evidence Sufficiency Layer brief, commit 6.

A thin policy layer over the existing ``retrieval/evidence`` stack.
The goal is *not* to re-implement retrieval; it's to make retrieval
*pharmacogenomically structured* so higher layers (sufficiency,
KG traversal, adaptive loop) can compose retrievers by strategy
rather than hardcoding a single path.

Contract
--------

Every concrete retriever in this subpackage implements one method:

    retrieve(query: BiomedicalQuery) -> RetrievalStrategyResult

``BiomedicalQuery`` is a frozen dataclass keyed on the four
pharmacogenomic scope fields — ``gene``, ``drug``, ``population``,
``genotype`` — plus an optional free-form ``question`` string. If
``question`` is empty the retriever composes a canonical query
from the tuple so the input space stays structured.

``RetrievalStrategyResult`` wraps the underlying
``retrieval.evidence.RetrievalResult`` unchanged and adds two
audit-oriented fields: ``strategy`` (the retriever that produced
it) and ``retrieval_priorities`` (a dict of strategy-specific
knobs the caller can inspect — e.g. a ``PopulationAwareRetriever``
records the per-doc boost it applied).

Scope firewall
--------------
* Every retriever rejects queries with an empty ``gene`` or ``drug``
  field at ``retrieve()`` time. ``population`` is typed as the
  closed ``SuperPopulation`` enum so a non-canonical code never
  reaches the retriever in the first place.
* No retriever in this subpackage introduces a new index or new
  document source. The dense baseline uses the existing
  ``VectorIndex`` + ``EvidenceRetriever``. Population-aware and
  graph-aware retrievers *re-rank* or *augment* the base result;
  they never retrieve outside the catalogued pharmacogenomic
  corpus.

Populated through phase 2:

    BiomedicalQuery               frozen query shape (commit 6)
    RetrievalStrategyResult       frozen result wrapper (commit 6)
    BiomedicalRetriever           ABC with retrieve() method (commit 6)
    DenseSemanticRetriever        wraps EvidenceRetriever (commit 6)
    PopulationAwareRetriever      pop-aware re-ranker (commit 6)
    GraphRetriever                KG-backed stub (commit 7)
    EvidenceSelector              diversity + dedup (commit 7)
    AdaptiveRetrievalController   sufficiency-aware loop (commit 8)
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from core.models.population import SuperPopulation
from retrieval.evidence.retriever import (
    EvidenceRetriever,
    RetrievalResult,
    RetrievedEvidence,
)
from retrieval.planner.query_planner import QueryPlanner


# ---------------------------------------------------------------------------
# Frozen shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BiomedicalQuery:
    """Frozen pharmacogenomic query.

    Scope keys match the rest of the evidence-sufficiency layer:

        gene         non-empty string (uppercased on construction
                     via the factory method ``BiomedicalQuery.new``)
        drug         non-empty string
        population   closed SuperPopulation enum
        genotype     optional string; defaults to 'unknown' so the
                     canonical query composition can still include it
        question     optional free-form prompt. Empty -> canonical
                     question is synthesized on demand via
                     ``effective_question``.

    Callers **must** use the ``BiomedicalQuery.new`` factory rather
    than the raw constructor. The factory validates gene/drug and
    coerces ``population`` from either a ``SuperPopulation`` or a
    canonical 3-letter code string — same discipline as
    ``EvidenceCoverageAnalyzer._coerce_population``.
    """

    gene: str
    drug: str
    population: SuperPopulation
    genotype: str = "unknown"
    question: str = ""

    @classmethod
    def new(
        cls,
        *,
        gene: str,
        drug: str,
        population: SuperPopulation | str,
        genotype: str = "unknown",
        question: str = "",
    ) -> "BiomedicalQuery":
        """Validate + coerce then build. Scope firewall at the type boundary."""

        if not gene or not str(gene).strip():
            raise ValueError("BiomedicalQuery.gene must be non-empty")
        if not drug or not str(drug).strip():
            raise ValueError("BiomedicalQuery.drug must be non-empty")
        if isinstance(population, SuperPopulation):
            pop = population
        elif isinstance(population, str) and population.strip():
            pop = SuperPopulation(population.strip().upper())
        else:
            raise ValueError(
                "BiomedicalQuery.population must be a SuperPopulation or a "
                f"canonical 3-letter code; got {population!r}"
            )
        return cls(
            gene=str(gene).strip().upper(),
            drug=str(drug).strip().lower(),
            population=pop,
            genotype=str(genotype).strip() or "unknown",
            question=str(question).strip(),
        )

    @property
    def effective_question(self) -> str:
        """Return ``question`` if non-empty, else a canonical composition.

        The canonical form is deterministic — same tuple always
        produces the same string — which lets the dense retriever
        and cache treat identical queries identically.
        """

        if self.question:
            return self.question
        return (
            f"{self.gene} {self.drug} {self.population.value} "
            f"{self.genotype} pharmacogenomic recommendation"
        ).strip()


@dataclass(frozen=True)
class RetrievalStrategyResult:
    """Frozen wrapper around a ``RetrievalResult`` with strategy context.

    Fields
    ------
    result                   the underlying ``RetrievalResult`` — its
                             fields (evidence, citations, total_retrieved)
                             are forwarded unchanged so downstream
                             consumers that already accept
                             ``RetrievalResult`` work without adaptation
    strategy                 name of the concrete retriever that
                             produced the result (e.g. 'dense_semantic',
                             'population_aware', 'graph_retrieval')
    query                    the ``BiomedicalQuery`` that was executed
    retrieval_priorities     strategy-specific audit dict. Keys are
                             free-form strings; values are primitive
                             (numbers / strings / lists of them) so
                             the whole result is JSON-safe. Populate
                             with whatever is useful for that retriever;
                             callers only introspect by key they own.
    created_at               ISO timestamp
    """

    result: RetrievalResult
    strategy: str
    query: BiomedicalQuery
    retrieval_priorities: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def evidence(self) -> list[RetrievedEvidence]:
        return list(self.result.evidence)

    @property
    def total_retrieved(self) -> int:
        return int(self.result.total_retrieved)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "query": {
                "gene": self.query.gene,
                "drug": self.query.drug,
                "population": self.query.population.value,
                "genotype": self.query.genotype,
                "effective_question": self.query.effective_question,
            },
            "total_retrieved": self.total_retrieved,
            "citation_ids": [c.citation_id for c in self.result.citations],
            "evidence_ids": [e.evidence_id for e in self.result.evidence],
            "retrieval_priorities": dict(self.retrieval_priorities),
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BiomedicalRetriever(abc.ABC):
    """Strategy interface every concrete retriever implements.

    Single method: ``retrieve(query) -> RetrievalStrategyResult``.
    Concrete retrievers MUST NOT mutate the underlying
    ``RetrievalResult``; they may wrap it with a different ordering
    or augment ``retrieval_priorities``, but the source evidence set
    and its citations are immutable.
    """

    #: Short identifier for the strategy, e.g. 'dense_semantic'.
    #: Used in ``RetrievalStrategyResult.strategy``.
    strategy_name: str = "biomedical_retriever"

    @abc.abstractmethod
    def retrieve(self, query: BiomedicalQuery) -> RetrievalStrategyResult:  # pragma: no cover
        """Execute retrieval for ``query`` and return a strategy result."""


# ---------------------------------------------------------------------------
# DenseSemanticRetriever — concrete baseline
# ---------------------------------------------------------------------------


@dataclass
class DenseSemanticRetriever(BiomedicalRetriever):
    """Strategy wrapper around the existing ``EvidenceRetriever``.

    The baseline. Does not re-rank, filter, or augment — delegates
    to ``QueryPlanner.plan`` + ``EvidenceRetriever.execute_plan``
    and hands the raw result back with ``strategy='dense_semantic'``.

    Having a concrete baseline in this subpackage matters for two
    reasons:

      1. The ``AdaptiveRetrievalController`` (commit 8) can swap
         strategies at runtime and falls back to dense if nothing
         else yields enough evidence.
      2. Re-ranking retrievers (like ``PopulationAwareRetriever``)
         compose *over* a base retriever. Having a shared concrete
         base means they don't reach directly into ``retrieval/``.
    """

    strategy_name: str = "dense_semantic"
    _retriever: EvidenceRetriever = field(default_factory=EvidenceRetriever)
    _planner: QueryPlanner = field(default_factory=QueryPlanner)
    top_k_per_query: int = 3

    def retrieve(self, query: BiomedicalQuery) -> RetrievalStrategyResult:
        plan = self._planner.plan(
            query.effective_question,
            gene=query.gene,
            drug=query.drug,
            population=query.population.value,
        )
        result = self._retriever.execute_plan(plan, top_k_per_query=self.top_k_per_query)
        return RetrievalStrategyResult(
            result=result,
            strategy=self.strategy_name,
            query=query,
            retrieval_priorities={
                "top_k_per_query": self.top_k_per_query,
                "plan_id": plan.plan_id,
                "sub_queries": [sq.query_id for sq in plan.sub_queries],
            },
        )


# ---------------------------------------------------------------------------
# PopulationAwareRetriever — re-ranker
# ---------------------------------------------------------------------------


# Same anchor table as the coverage analyzer. Single source of truth
# for "does this document mention population X". Centralised in
# ``core.models.population_mentions`` so both components share exactly
# the same vocabulary.
from core.models.population_mentions import mentions_population  # noqa: E402


@dataclass
class PopulationAwareRetriever(BiomedicalRetriever):
    """Wraps a base retriever; re-ranks by population alignment.

    Scoring
    -------
    For each piece of retrieved evidence the retriever computes a
    ``population_boost`` in the range ``[-penalty, +boost]``:

        +boost     evidence mentions the query's super-population
        0          evidence mentions no super-population at all
        -penalty   evidence mentions a DIFFERENT super-population
                   (and not the query's)

    The final ordering uses
    ``adjusted_score = relevance_score + population_boost``.
    Ties are broken by the original relevance_score. Documents with
    a non-zero boost surface at the top; unboosted evidence keeps
    its original order among itself.

    Configuration
    -------------
    * ``boost``   — default 0.15
    * ``penalty`` — default 0.10 (smaller than boost: we'd rather
                    include a mildly-mismatched source than drop it,
                    but we do prefer aligned ones)

    Population is a first-class reasoning dimension here, not
    metadata: it *moves evidence in the returned ordering*. That is
    the whole point of the layer.

    Scope firewall
    --------------
    Rebuilds neither the index nor the planner. Takes any
    ``BiomedicalRetriever`` as the base, defaulting to the dense
    baseline. Never touches ``retrieval_priorities`` written by the
    base retriever — adds its own ``population_priorities`` keys.
    """

    base: BiomedicalRetriever = field(default_factory=DenseSemanticRetriever)
    boost: float = 0.15
    penalty: float = 0.10
    strategy_name: str = "population_aware"

    def retrieve(self, query: BiomedicalQuery) -> RetrievalStrategyResult:
        base_result = self.base.retrieve(query)

        # Re-rank over the base result's evidence. Walk each evidence
        # passage, classify population mention, compute boost, then
        # stable-sort by (adjusted_score desc, original_index asc).
        evidence_with_scores: list[tuple[float, int, RetrievedEvidence, float]] = []
        per_doc_boosts: list[dict[str, Any]] = []
        for idx, ev in enumerate(base_result.result.evidence):
            boost_value = self._classify_and_score(ev, query.population)
            adjusted = float(ev.relevance_score) + boost_value
            evidence_with_scores.append((adjusted, idx, ev, boost_value))
            per_doc_boosts.append(
                {
                    "evidence_id": ev.evidence_id,
                    "citation_id": ev.citation.citation_id,
                    "original_score": float(ev.relevance_score),
                    "boost": round(boost_value, 4),
                    "adjusted_score": round(adjusted, 4),
                }
            )

        # Stable sort: primary by adjusted_score desc; tiebreak by
        # original index asc so unchanged ordering among unboosted
        # passages is preserved.
        evidence_with_scores.sort(key=lambda t: (-t[0], t[1]))

        reranked_evidence = [ev for _, _, ev, _ in evidence_with_scores]

        # New RetrievalResult — note: we don't mutate base_result.result
        # (it's frozen). We construct a sibling RetrievalResult with the
        # reranked evidence list. Citations are recomputed from the new
        # evidence order so the first citation matches the top-ranked
        # passage, which callers rely on for "primary citation".
        reranked_result = RetrievalResult(
            plan_id=base_result.result.plan_id,
            query=base_result.result.query,
            evidence=reranked_evidence,
            citations=list(
                {
                    ev.citation.citation_id: ev.citation for ev in reranked_evidence
                }.values()
            ),
            total_retrieved=len(reranked_evidence),
            timestamp=base_result.result.timestamp,
        )

        priorities: dict[str, Any] = dict(base_result.retrieval_priorities)
        priorities.update(
            {
                "population_strategy": self.strategy_name,
                "population_target": query.population.value,
                "population_boost_applied": self.boost,
                "population_penalty_applied": self.penalty,
                "population_priorities": per_doc_boosts,
            }
        )

        return RetrievalStrategyResult(
            result=reranked_result,
            strategy=self.strategy_name,
            query=query,
            retrieval_priorities=priorities,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _classify_and_score(
        self, ev: RetrievedEvidence, target: SuperPopulation
    ) -> float:
        """Return the signed population boost for ``ev`` given ``target``.

        Inspects the evidence's title + content (capped) for
        population anchors. Uses the same closed-table matcher the
        coverage analyzer uses, so both components speak about
        population with the same vocabulary.
        """

        # Evidence content can be long; cap at 400 chars like the
        # analyzer does for retrieval_results. Title is short; always
        # include it.
        hay = f"{ev.citation.title or ''} {str(ev.content or '')[:400]}"
        if mentions_population(hay, target):
            return float(self.boost)

        # Only penalise if the doc aligns with a *different* population.
        # Mentioning none -> no penalty.
        for pop in SuperPopulation:
            if pop is target:
                continue
            if mentions_population(hay, pop):
                return float(-self.penalty)
        return 0.0


__all__ = [
    "BiomedicalQuery",
    "RetrievalStrategyResult",
    "BiomedicalRetriever",
    "DenseSemanticRetriever",
    "PopulationAwareRetriever",
]
