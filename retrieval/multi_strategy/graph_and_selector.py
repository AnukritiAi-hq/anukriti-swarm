"""``GraphRetriever`` (stub) + ``EvidenceSelector`` (diversity + dedup).

Phase 2 of the Evidence Sufficiency Layer brief, commit 7.

Two classes, both shipped in their final public shape. The
``GraphRetriever`` *surface* is final; its internals are a
documented stub until phase 3 lands the pharmacogenomic knowledge
graph. The ``EvidenceSelector`` is complete and deterministic.

Design discipline
-----------------

Neither class introduces a new document source, a new index, or a
new API surface outside the ``BiomedicalRetriever`` ABC. The
``EvidenceSelector`` *merges* multiple strategy outputs into a
single ``RetrievalStrategyResult``; it does not run retrieval
itself. No LLM anywhere; all decisions are pure functions of
structured inputs.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from core.models.population import SuperPopulation
from retrieval.evidence.retriever import (
    Citation,
    RetrievalResult,
    RetrievedEvidence,
)
from retrieval.multi_strategy.biomedical_retriever import (
    BiomedicalQuery,
    BiomedicalRetriever,
    RetrievalStrategyResult,
)


# ---------------------------------------------------------------------------
# GraphRetriever — phase-3 stub with a final public surface
# ---------------------------------------------------------------------------


@dataclass
class GraphRetriever(BiomedicalRetriever):
    """Knowledge-graph-aware retrieval strategy.

    **Public surface is final; internals are a stub.**

    Phase 3 of the brief ships the ``PharmacogenomicKnowledgeGraph``
    plus ``MultiHopReasoner`` / ``PathEvidenceRetriever``. When that
    lands, the stub body is replaced by a thin adapter: compose
    multi-hop paths for the query's ``(gene, drug, population,
    genotype)`` tuple, turn each path's ``supported_by`` edges into
    ``RetrievedEvidence`` entries, return them in a
    ``RetrievalStrategyResult``.

    Until phase 3 the retriever returns an *empty* result — no
    evidence, no citations — with a ``retrieval_priorities`` marker
    that identifies the pending-state explicitly. That keeps callers
    (``EvidenceSelector``, ``AdaptiveRetrievalController``) able to
    wire the strategy today without branching on "graph backend
    exists?": an empty result is a valid result.

    Why ship an empty-but-final surface instead of raising?
      1. ``AdaptiveRetrievalController`` (commit 8) iterates
         strategies and stops when sufficiency is reached. A
         raising stub would force special-casing.
      2. The brief asks for five named classes on the retriever
         side; shipping only four leaves a gap in the public audit.
      3. The stub is discoverable: callers see
         ``retrieval_priorities['pending'] == 'phase_3_knowledge_graph'``
         and know the class is provisioned but unpopulated.

    Scope firewall
    --------------
    Even in stub form the retriever validates the query's
    pharmacogenomic scope (gene, drug, population). A caller that
    passes a malformed query is rejected here with the same
    ``ValueError`` any other retriever raises via
    ``BiomedicalQuery.new``. Shipping the gate now means the
    behaviour is stable across the phase-2/phase-3 transition.
    """

    strategy_name: str = "graph_retrieval"

    def retrieve(self, query: BiomedicalQuery) -> RetrievalStrategyResult:
        # Scope enforcement — same discipline as other retrievers,
        # independent of the stub body.
        if not query.gene or not query.drug:
            raise ValueError(
                "GraphRetriever requires a gene + drug on the query; "
                f"got gene={query.gene!r} drug={query.drug!r}"
            )
        if not isinstance(query.population, SuperPopulation):
            raise TypeError(
                "GraphRetriever requires SuperPopulation on the query"
            )

        empty_result = RetrievalResult(
            plan_id=f"graph-stub:{query.gene}:{query.drug}",
            query=query.effective_question,
            evidence=[],
            citations=[],
            total_retrieved=0,
        )

        return RetrievalStrategyResult(
            result=empty_result,
            strategy=self.strategy_name,
            query=query,
            retrieval_priorities={
                "pending": "phase_3_knowledge_graph",
                "gene": query.gene,
                "drug": query.drug,
                "population": query.population.value,
                "genotype": query.genotype,
                "note": (
                    "GraphRetriever public surface is final; multi-hop "
                    "reasoning lands in phase 3 of the Evidence Sufficiency "
                    "Layer brief. Until then this returns an empty result "
                    "so adaptive loops can still enumerate strategies."
                ),
            },
        )


# ---------------------------------------------------------------------------
# EvidenceSelector — diversity + dedup
# ---------------------------------------------------------------------------


# Strategy priority tiebreak order. Named retrievers come first when
# several strategies tie on score; unknown strategies fall through to
# the trailing 'dense_semantic' slot so the merger always has a stable
# answer. Extending the order is a code change.
_STRATEGY_PRIORITY: tuple[str, ...] = (
    "graph_retrieval",
    "population_aware",
    "dense_semantic",
)


def _strategy_rank(name: str) -> int:
    """Return a stable rank for a strategy name; lower is more preferred."""

    try:
        return _STRATEGY_PRIORITY.index(name)
    except ValueError:
        return len(_STRATEGY_PRIORITY)  # unknowns sink to the bottom


@dataclass(frozen=True)
class _EvidenceCandidate:
    """Per-candidate record the selector produces internally.

    Frozen so the scoring pass can re-use these as immutable keys.
    """

    evidence: RetrievedEvidence
    strategy: str
    strategy_rank: int
    adjusted_score: float


@dataclass
class EvidenceSelector:
    """Deterministic diversity + dedup selector over strategy outputs.

    Inputs
    ------
    ``select(results, *, query=None, max_per_source=3, max_total=12)``

    ``results`` is an iterable of ``RetrievalStrategyResult`` from
    any number of retrievers; the selector merges them into one.
    ``query`` is optional — if omitted the first input result's
    query is used for the returned wrapper; if supplied it must
    match the input queries' ``(gene, drug, population, genotype)``
    tuple (deterministic sanity check to stop cross-scope mixing).

    Behaviour (deterministic, LLM-free)
    -----------------------------------

    1. Dedup by ``citation.citation_id``. First occurrence wins.
       Ordering within duplicates is determined by (adjusted_score
       desc, strategy_rank asc, citation_id asc) so two identical
       merges produce byte-identical output.

    2. Diversity cap per-source. Count occurrences by
       ``citation.source.value`` (CPIC / PharmGKB / PubMed / FDA)
       and drop any candidate that would exceed ``max_per_source``.
       Evidence from under-represented sources is preferred over
       over-represented ones at the dropping boundary — the
       selector surfaces *one of each source* before returning to
       best-score.

    3. Overall cap. Truncate to ``max_total`` after steps 1+2.

    4. Stable output ordering. Primary: adjusted_score desc.
       Secondary: strategy_rank asc. Tertiary: citation_id asc
       (lexical). Every merge of identical inputs is identical.

    ``adjusted_score`` source
    -------------------------
    The selector reads whatever score is already on the evidence:
    ``RetrievedEvidence.relevance_score`` for dense results, plus
    the population-boost adjustment when the producing strategy
    was ``population_aware`` and the priorities dict carries a
    per-doc boost entry. Other strategies are treated as
    ``relevance_score`` unchanged. No LLM re-scoring.

    Scope firewall
    --------------
    The selector refuses to merge results whose queries disagree on
    the pharmacogenomic tuple. It does not interpret content; it
    combines *already-retrieved* evidence by citation id and source.
    """

    max_per_source: int = 3
    max_total: int = 12

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select(
        self,
        results: Iterable[RetrievalStrategyResult],
        *,
        query: BiomedicalQuery | None = None,
        max_per_source: int | None = None,
        max_total: int | None = None,
    ) -> RetrievalStrategyResult:
        """Merge strategy outputs into one diverse, deduped result."""

        results_list = [r for r in results if r is not None]
        if not results_list:
            raise ValueError("EvidenceSelector.select requires ≥1 input result")

        # Cross-scope sanity check: all input queries must share scope.
        reference_query = query or results_list[0].query
        for r in results_list:
            if not self._same_scope(r.query, reference_query):
                raise ValueError(
                    "EvidenceSelector cannot merge results across "
                    "different pharmacogenomic scopes "
                    f"({r.query.gene}/{r.query.drug}/{r.query.population.value} "
                    f"vs {reference_query.gene}/{reference_query.drug}/"
                    f"{reference_query.population.value})"
                )

        cap_per_src = int(self.max_per_source if max_per_source is None else max_per_source)
        cap_total = int(self.max_total if max_total is None else max_total)

        # 1. Build candidates with per-strategy boost lookup.
        candidates = list(self._expand_candidates(results_list))

        # 2. Stable sort by (score desc, strategy_rank asc, citation_id asc).
        candidates.sort(
            key=lambda c: (
                -c.adjusted_score,
                c.strategy_rank,
                c.evidence.citation.citation_id,
            )
        )

        # 3. Dedup by citation_id preserving the winning order.
        seen: set[str] = set()
        deduped: list[_EvidenceCandidate] = []
        for cand in candidates:
            cid = cand.evidence.citation.citation_id
            if cid in seen:
                continue
            seen.add(cid)
            deduped.append(cand)

        # 4. Diversity pass: cap per-source while preserving order;
        # favour surfacing one-of-each-source before going deeper.
        selected = self._apply_diversity_cap(deduped, cap_per_src, cap_total)

        # 5. Assemble a new RetrievalResult.
        selected_evidence = [c.evidence for c in selected]
        citations: list[Citation] = list(
            {
                c.evidence.citation.citation_id: c.evidence.citation
                for c in selected
            }.values()
        )
        merged_result = RetrievalResult(
            plan_id=self._merged_plan_id(results_list),
            query=reference_query.effective_question,
            evidence=selected_evidence,
            citations=citations,
            total_retrieved=len(selected_evidence),
        )

        source_counts = Counter(
            c.evidence.citation.source.value for c in selected
        )
        priorities: dict[str, Any] = {
            "strategies_merged": [r.strategy for r in results_list],
            "source_counts": dict(source_counts),
            "candidate_count_before_dedup": len(candidates),
            "candidate_count_after_dedup": len(deduped),
            "selected_count": len(selected),
            "max_per_source": cap_per_src,
            "max_total": cap_total,
        }

        return RetrievalStrategyResult(
            result=merged_result,
            strategy="evidence_selector",
            query=reference_query,
            retrieval_priorities=priorities,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _same_scope(a: BiomedicalQuery, b: BiomedicalQuery) -> bool:
        return (
            a.gene == b.gene
            and a.drug == b.drug
            and a.population is b.population
            and a.genotype == b.genotype
        )

    @staticmethod
    def _merged_plan_id(results: list[RetrievalStrategyResult]) -> str:
        parts = sorted({r.result.plan_id for r in results})
        return "selector:" + "+".join(parts)

    @staticmethod
    def _population_boost_lookup(
        priorities: Mapping[str, Any],
    ) -> dict[str, float]:
        """Extract the per-doc population boost map when present."""

        entries = priorities.get("population_priorities")
        if not entries:
            return {}
        return {
            str(e["evidence_id"]): float(e.get("boost", 0.0))
            for e in entries
            if "evidence_id" in e
        }

    def _expand_candidates(
        self, results: list[RetrievalStrategyResult]
    ) -> Iterable[_EvidenceCandidate]:
        for sr in results:
            boost_map = self._population_boost_lookup(sr.retrieval_priorities)
            rank = _strategy_rank(sr.strategy)
            for ev in sr.result.evidence:
                boost = boost_map.get(ev.evidence_id, 0.0)
                yield _EvidenceCandidate(
                    evidence=ev,
                    strategy=sr.strategy,
                    strategy_rank=rank,
                    adjusted_score=round(float(ev.relevance_score) + boost, 6),
                )

    @staticmethod
    def _apply_diversity_cap(
        deduped: list[_EvidenceCandidate],
        cap_per_src: int,
        cap_total: int,
    ) -> list[_EvidenceCandidate]:
        """Two-pass diversity cap: first surface 1 of each source, then fill.

        Pass A: walk candidates in their already-sorted order, admit
        the first candidate from each unique source (up to cap_total).
        Pass B: continue walking and admit further candidates, capping
        per-source at ``cap_per_src`` and overall at ``cap_total``.

        This guarantees every represented source gets at least one
        slot before any source monopolises.
        """

        if cap_per_src <= 0 or cap_total <= 0:
            return []

        selected: list[_EvidenceCandidate] = []
        per_source: Counter[str] = Counter()
        seen_sources: set[str] = set()

        # Pass A — diversity anchor
        for cand in deduped:
            if len(selected) >= cap_total:
                break
            src = cand.evidence.citation.source.value
            if src in seen_sources:
                continue
            selected.append(cand)
            per_source[src] += 1
            seen_sources.add(src)

        # Pass B — fill respecting per-source cap
        if len(selected) < cap_total:
            for cand in deduped:
                if cand in selected:
                    continue
                if len(selected) >= cap_total:
                    break
                src = cand.evidence.citation.source.value
                if per_source[src] >= cap_per_src:
                    continue
                selected.append(cand)
                per_source[src] += 1

        # Re-sort post-admission by the primary key so the output
        # reflects final ranking, not pass order.
        selected.sort(
            key=lambda c: (
                -c.adjusted_score,
                c.strategy_rank,
                c.evidence.citation.citation_id,
            )
        )
        return selected


__all__ = [
    "GraphRetriever",
    "EvidenceSelector",
]
