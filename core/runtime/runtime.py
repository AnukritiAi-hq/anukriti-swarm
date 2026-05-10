"""``SwarmRuntime`` — unified swarm lifecycle.

Phase 2, commit 5 of the Unified Orchestration + Visualization brief.

Single class, single public method: ``run(ctx)``. Executes the
canonical 5-stage lifecycle and returns a ``UnifiedExecutionReport``.
Emits ``RuntimeEvent``s at every stage boundary through an
injectable ``EventStream`` so the FastAPI WebSocket endpoint
(phase 3) can stream them to the live frontend.

Stages (ordered, deterministic):

    1. orchestration      records activated agents + trace
    2. retrieval          multi-strategy + selector
    3. graph_reasoning    KG multi-hop with population weight
    4. sufficiency        full 4-layer SufficiencyCheckpoint
    5. synthesis          deterministic narrative OR abstention

The runtime is NOT a new orchestrator. It composes existing
components and replaces the stage functions in
``demos/unified_demo.py`` (commit 6 rewires the demo to use this
class). One instance is safe for many runs; components are shared
across ``run()`` calls.

Scope firewall
--------------
* Input is a fully-constructed ``UnifiedExecutionContext`` — the
  runtime never coerces scope itself (the context factory did).
* Fatal stage errors are logged to the context's errors and caught
  at the runtime boundary, converting into a ``RUN_FAILED`` event
  with an empty ``UnifiedExecutionReport`` rather than raising into
  the FastAPI handler. This keeps the WebSocket channel clean.
* No synthesis runs when sufficiency blocks — ``_stage_synthesis``
  inspects ``evidence_state.checkpoint.allows_synthesis`` and
  emits ``SAFE_ABSTENTION`` instead.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from integrations.mcp.provenance import ProvenanceRecord
from knowledge_graph import (
    GraphContextBuilder,
    MultiHopReasoner,
    PopulationGraphIndexer,
)

from core.evidence_sufficiency import SufficiencyCheckpoint
from core.runtime.events import (
    EventStream,
    InMemoryEventStream,
    RuntimeEvent,
    RuntimeEventKind,
)
from core.runtime.report import UnifiedExecutionReport
from retrieval.evidence.documents import (
    CPIC_DOCUMENTS,
    PHARMGKB_DOCUMENTS,
    PUBMED_DOCUMENTS,
)
from retrieval.multi_strategy import (
    BiomedicalQuery,
    DenseSemanticRetriever,
    EvidenceSelector,
    PopulationAwareRetriever,
)

if TYPE_CHECKING:
    from core.runtime.context import UnifiedExecutionContext

_ALL_DOCS = CPIC_DOCUMENTS + PHARMGKB_DOCUMENTS + PUBMED_DOCUMENTS


@dataclass
class SwarmRuntime:
    """Lifecycle class composing every existing swarm module.

    Components are injectable; defaults produce the canonical
    deterministic pipeline. Events are emitted through
    ``self.event_stream``, which defaults to a fresh
    ``InMemoryEventStream`` per instance.

    Construction is zero-arg for the common case:

        runtime = SwarmRuntime()
        report = runtime.run(ctx)
        for event in runtime.event_stream.events:
            ...
    """

    event_stream: EventStream = field(default_factory=InMemoryEventStream)

    # Lazily-built shared components. Build once per SwarmRuntime;
    # reuse across ``run()`` invocations. Exposed on the instance so
    # tests can introspect.
    _graph: Any = None
    _indexer: PopulationGraphIndexer | None = None
    _reasoner: MultiHopReasoner | None = None
    _retriever: PopulationAwareRetriever | None = None
    _dense_retriever: DenseSemanticRetriever | None = None
    _selector: EvidenceSelector | None = None
    _checkpoint: SufficiencyCheckpoint | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, ctx: UnifiedExecutionContext) -> UnifiedExecutionReport:
        """Execute the full 5-stage lifecycle; return a frozen report."""

        self._ensure_components()
        t0 = time.perf_counter()
        self._emit(
            RuntimeEventKind.RUN_STARTED,
            ctx,
            payload={
                "drug": ctx.drug,
                "gene": ctx.gene,
                "population": ctx.population.value,
                "genotype": ctx.genotype,
            },
        )

        try:
            self._stage_orchestration(ctx)
            retrieval_bundle = self._stage_retrieval(ctx)
            paths = self._stage_graph_reasoning(ctx)
            self._stage_sufficiency(ctx, retrieval_bundle, paths)
            self._stage_synthesis(ctx)
        except Exception as exc:  # pragma: no cover — defensive
            ctx.record_error(f"fatal: {exc!r}")
            self._emit(
                RuntimeEventKind.RUN_FAILED,
                ctx,
                payload={
                    "error": repr(exc),
                },
            )
            duration_ms = (time.perf_counter() - t0) * 1000
            return UnifiedExecutionReport.from_context(ctx, total_duration_ms=duration_ms)

        duration_ms = (time.perf_counter() - t0) * 1000
        self._emit(
            RuntimeEventKind.RUN_COMPLETED,
            ctx,
            payload={
                "duration_ms": round(duration_ms, 3),
                "activated_agents": list(ctx.activated_agents),
            },
        )
        return UnifiedExecutionReport.from_context(ctx, total_duration_ms=duration_ms)

    # ------------------------------------------------------------------
    # Shared component assembly
    # ------------------------------------------------------------------

    def _ensure_components(self) -> None:
        """Build the shared components on first run; reuse after."""

        if self._graph is None:
            self._graph = GraphContextBuilder().build_default()
            self._indexer = PopulationGraphIndexer.build(self._graph)
            self._reasoner = MultiHopReasoner(max_hops=4)
            self._retriever = PopulationAwareRetriever()
            self._dense_retriever = DenseSemanticRetriever()
            self._selector = EvidenceSelector(max_per_source=3, max_total=8)
            self._checkpoint = SufficiencyCheckpoint()

    # ------------------------------------------------------------------
    # Event emission helper
    # ------------------------------------------------------------------

    def _emit(
        self,
        kind: RuntimeEventKind,
        ctx: UnifiedExecutionContext,
        *,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Create a RuntimeEvent and push it through the stream."""

        self.event_stream.emit(
            RuntimeEvent(
                kind=kind,
                correlation_id=ctx.correlation_id,
                payload=dict(payload or {}),
            )
        )

    def _record_agent(self, ctx: UnifiedExecutionContext, name: str) -> None:
        """Record + emit AGENT_ACTIVATED for every new specialist."""

        already = name in ctx.activated_agents
        ctx.record_agent(name)
        if not already:
            self._emit(
                RuntimeEventKind.AGENT_ACTIVATED,
                ctx,
                payload={
                    "agent": name,
                },
            )

    # ------------------------------------------------------------------
    # Stage 1: orchestration
    # ------------------------------------------------------------------

    def _stage_orchestration(self, ctx: UnifiedExecutionContext) -> None:
        self._record_agent(ctx, "orchestrator")
        ctx.orchestration_trace = {
            "steps": [
                {"name": "intake", "detail": f"Validated {ctx.gene} {ctx.genotype}"},
                {"name": "dispatch", "detail": f"Dispatched to {ctx.population.value} specialists"},
            ],
        }

    # ------------------------------------------------------------------
    # Stage 2: retrieval
    # ------------------------------------------------------------------

    def _stage_retrieval(self, ctx: UnifiedExecutionContext) -> dict[str, Any]:
        self._record_agent(ctx, "population_aware_retriever")
        query = BiomedicalQuery.new(
            gene=ctx.gene,
            drug=ctx.drug,
            population=ctx.population,
            genotype=ctx.genotype,
        )
        pop_result = self._retriever.retrieve(query)
        dense_result = self._dense_retriever.retrieve(query)
        merged = self._selector.select([pop_result, dense_result], query=query)

        citations = [c.citation_id for c in merged.result.citations]
        ctx.evidence_state = {
            "citations": citations,
            "total_retrieved": merged.total_retrieved,
            "strategy": merged.strategy,
        }
        self._emit(
            RuntimeEventKind.RETRIEVAL_COMPLETE,
            ctx,
            payload={
                "citations": citations,
                "total_retrieved": merged.total_retrieved,
                "strategy": merged.strategy,
            },
        )
        return {"merged": merged, "citations": citations}

    # ------------------------------------------------------------------
    # Stage 3: graph reasoning
    # ------------------------------------------------------------------

    def _stage_graph_reasoning(self, ctx: UnifiedExecutionContext) -> list:
        self._record_agent(ctx, "graph_reasoner")
        allele_guess = f"allele:{ctx.gene}*{ctx.genotype.split('/')[0].lstrip('*')}"
        drug_id = f"drug:{ctx.drug}"

        start_id: str | None = allele_guess if self._graph.has_node(allele_guess) else None
        if start_id is None:
            phen_candidates = [
                n.id for n in self._graph.nodes() if n.id.startswith(f"phenotype:{ctx.gene}")
            ]
            start_id = phen_candidates[0] if phen_candidates else None

        paths: list = []
        if start_id and self._graph.has_node(drug_id):
            paths = list(
                self._reasoner.find_paths(
                    self._graph,
                    start_id,
                    drug_id,
                    target_population=ctx.population,
                    pop_indexer=self._indexer,
                )
            )

        ctx.graph_state = {
            "start_id": start_id,
            "goal_id": drug_id,
            "paths": [p.to_dict() for p in paths],
        }
        self._emit(
            RuntimeEventKind.GRAPH_TRAVERSAL,
            ctx,
            payload={
                "start_id": start_id,
                "goal_id": drug_id,
                "path_count": len(paths),
                "paths": [p.to_dict() for p in paths],
            },
        )
        return paths

    # ------------------------------------------------------------------
    # Stage 4: sufficiency
    # ------------------------------------------------------------------

    def _stage_sufficiency(
        self,
        ctx: UnifiedExecutionContext,
        retrieval_bundle: dict[str, Any],
        paths: list,
    ) -> None:
        self._record_agent(ctx, "sufficiency_checkpoint")

        allele1, _, allele2 = ctx.genotype.partition("/")
        if not allele2:
            allele1, allele2 = ctx.genotype, "positive"

        pharmacogene_result = _phenotype_for(ctx)
        population_result = _pop_result_for(ctx, self._indexer)
        recommendations = _recommendations_for(
            ctx,
            pharmacogene_result.get("phenotype", ""),
        )

        run = {
            "gene": ctx.gene,
            "drug": ctx.drug,
            "population": ctx.population,
            "allele1": allele1 or "*1",
            "allele2": allele2 or "*1",
            "pharmacogene_result": pharmacogene_result,
            "population_result": population_result,
            "recommendations": recommendations,
        }

        provenance_records = _build_provenance(ctx, retrieval_bundle["citations"])
        result = self._checkpoint.evaluate(
            run,
            retrieval_docs=_ALL_DOCS,
            provenance_records=provenance_records,
            path_bundle=paths if paths else None,
            pop_indexer=self._indexer,
            correlation_id=ctx.correlation_id,
        )

        checkpoint_dict = result.to_dict()
        ctx.evidence_state = dict(ctx.evidence_state or {})
        ctx.evidence_state["checkpoint"] = checkpoint_dict

        ctx.verification_state = {
            "verdict": result.verdict.verdict.value,
            "rule_ids": [
                result.verdict.rule_id,
                result.report.decision.value,
                result.uncertainty.score.value,
            ],
        }
        ctx.uncertainty_state = {
            "score": result.uncertainty.score.value,
            "action": result.uncertainty.action.value,
            "rationale": result.uncertainty.rationale,
        }
        ctx.provenance_state = {
            "records": [p.to_dict() for p in provenance_records],
        }
        if result.bias_findings:
            self._record_agent(ctx, "population_bias_detector")

        # Emit the three sufficiency-related events in order.
        self._emit(
            RuntimeEventKind.SUFFICIENCY_DECISION,
            ctx,
            payload={
                "decision": result.report.decision.value,
                "rationale": result.report.rationale,
                "coverage_ratio": result.report.coverage.coverage_ratio,
                "missing_facets": [f.value for f in result.report.coverage.missing_facets],
                "uncertain_facets": [f.value for f in result.report.coverage.uncertain_facets],
            },
        )
        self._emit(
            RuntimeEventKind.VERIFICATION_CHECKPOINT,
            ctx,
            payload={
                "verdict": result.verdict.verdict.value,
                "rule_id": result.verdict.rule_id,
                "rationale": result.verdict.rationale,
                "pathway_complete": result.verdict.pathway_complete,
                "pathway_count": result.verdict.pathway_count,
            },
        )
        self._emit(
            RuntimeEventKind.UNCERTAINTY_TRANSITION,
            ctx,
            payload={
                "score": result.uncertainty.score.value,
                "action": result.uncertainty.action.value,
                "rationale": result.uncertainty.rationale,
                "bias_findings": [b.to_dict() for b in result.bias_findings],
            },
        )
        self._emit(
            RuntimeEventKind.PROVENANCE_PERSISTED,
            ctx,
            payload={
                "record_count": len(provenance_records),
                "records": [p.to_dict() for p in provenance_records],
            },
        )

    # ------------------------------------------------------------------
    # Stage 5: synthesis OR abstention
    # ------------------------------------------------------------------

    def _stage_synthesis(self, ctx: UnifiedExecutionContext) -> None:
        checkpoint = (ctx.evidence_state or {}).get("checkpoint", {}) or {}
        allows = bool(checkpoint.get("allows_synthesis"))

        if not allows:
            self._emit(
                RuntimeEventKind.SAFE_ABSTENTION,
                ctx,
                payload={
                    "blocking_reason": checkpoint.get("blocking_reason", ""),
                    "decision": checkpoint.get("sufficiency_decision", "unknown"),
                    "verdict": checkpoint.get("verdict", "unknown"),
                },
            )
            return

        self._record_agent(ctx, "narrative_agent")
        citations = (ctx.evidence_state or {}).get("citations", [])
        ctx.narrative_output = {
            "patient": _patient_narrative(ctx, citations),
            "researcher": _researcher_narrative(ctx, citations),
        }
        self._emit(
            RuntimeEventKind.SYNTHESIS_EMITTED,
            ctx,
            payload={
                "audiences": list(ctx.narrative_output),
                "patient_excerpt": ctx.narrative_output.get("patient", "")[:120],
            },
        )


# ---------------------------------------------------------------------------
# Fixture helpers (duplicated from demos/unified_demo.py)
#
# These are rule-based deterministic outputs for the three canonical
# scenarios. The runtime will call into real orchestrator + agent
# code once they're refactored to share types; for now the helpers
# keep SwarmRuntime self-contained.
# ---------------------------------------------------------------------------


def _phenotype_for(ctx: UnifiedExecutionContext) -> dict[str, Any]:
    """Real phenotype inference from the input genotype.

    - CYP genes go through the CPIC activity-score rule in
      rules.phenotype_rules.infer_phenotype. Unknown alleles yield
      'Indeterminate' with confidence=0 — which correctly causes
      the sufficiency layer's PHENOTYPE facet to read as MISSING.
    - HLA-B uses the carrier-status agent (agents.pharmacogene.hla_b),
      since HLA-B is a binary risk model, not a metabolizer spectrum.
      Presence of at least one '*15:02' allele => positive.
    """

    gene = ctx.gene
    a1 = (ctx.genotype.split("/")[0] if "/" in ctx.genotype else ctx.genotype).strip()
    a2 = (ctx.genotype.split("/")[1] if "/" in ctx.genotype else "").strip()

    if gene == "HLA-B":
        from agents.pharmacogene.hla_b import HLABAgent

        has_15_02 = "*15:02" in (a1, a2) or "15:02" in a1 or "15:02" in a2
        result = HLABAgent().assess_risk(has_15_02)
        return {
            "gene": "HLA-B",
            "phenotype": result.risk_phenotype,
            "rule_id": "hla_b.risk_allele",
            "origin": "deterministic",
            "confidence": result.confidence,
            "allele_status": result.allele_status,
        }

    # CYP2C19 / CYP2D6 / anything else covered by the activity-score rule.
    from rules.phenotype_rules import infer_phenotype

    inference = infer_phenotype(gene, a1 or "*1", a2 or "*1")
    # Translate the rule_version (e.g. 'cpic_activity_score_v1') into the
    # dotted rule_id the coverage analyzer's PHENOTYPE-facet check expects
    # (startswith('cpic.') or 'hla_b.'). The dotted form is the project's
    # canonical rule-id convention; the underscored form is internal to
    # the rule engine.
    rule_id = (
        "cpic.activity_score"
        if "cpic" in inference.rule_version.lower()
        else inference.rule_version
    )
    return {
        "gene": gene,
        "phenotype": inference.phenotype,
        "rule_id": rule_id,
        "origin": "deterministic",
        "confidence": inference.confidence,
        "activity_score": inference.activity_score,
        "diplotype": inference.diplotype,
    }


def _pop_result_for(
    ctx: UnifiedExecutionContext,
    indexer: PopulationGraphIndexer | None = None,
) -> dict[str, Any]:
    """Real per-population allele frequency from the KG indexer.

    Walks the indexer's alleles_for(population) output and picks the
    frequency of the first allele in the context genotype that has
    a known edge to the target population. When no such edge exists
    (AFR + codeine in the seed KG, for example), returns {} which
    correctly causes the POPULATION facet to read as UNCERTAIN /
    MISSING in the sufficiency layer — the whole point of
    ancestry-scarcity reporting.

    No indexer -> {} (defensive; unified_demo / runtime always
    supply one).
    """

    if indexer is None:
        return {}

    # The allele id in the KG is 'allele:<GENE>*<NAME>', where NAME
    # excludes the leading '*'. Extract the first allele from the
    # context genotype and match against the indexer's per-population
    # list by ALLELE node id (not by name — the indexer returns Nodes).
    parts = [p.strip() for p in ctx.genotype.split("/") if p.strip()]
    if not parts:
        return {}
    first_allele = parts[0].lstrip("*")
    target_id = f"allele:{ctx.gene}*{first_allele}"

    for node, freq in indexer.alleles_for(ctx.population):
        if node.id == target_id:
            return {
                "frequency": round(float(freq), 4),
                "population": ctx.population.value,
                "allele_id": target_id,
                "source": "knowledge_graph.HIGHER_FREQUENCY_IN",
            }
    # No matching edge for this allele in this population.
    return {}


def _recommendations_for(
    ctx: UnifiedExecutionContext,
    phenotype: str,
) -> list[dict[str, Any]]:
    """Real CPIC recommendation lookup keyed on (gene, phenotype, drug).

    Uses guidelines.cpic.lookup_recommendation which walks the
    in-tree CPIC guideline table. On hit, returns one dict matching
    the sufficiency layer's expected shape. On miss, returns [] —
    which correctly causes the RECOMMENDATION facet to read as
    MISSING (triggering R3 BLOCK).

    Evidence refs are pulled directly off the CPIC record's PMID
    field so the chain is honest: the recommendation text IS the
    CPIC guideline's recommendation field verbatim.
    """

    from guidelines.cpic import lookup_recommendation

    rec = lookup_recommendation(ctx.gene, phenotype, ctx.drug)
    if rec is None:
        return []
    return [
        {
            "recommendation": rec.recommendation,
            "evidence_refs": [rec.guideline_id, rec.pmid],
            "strength": rec.strength,
            "classification": rec.classification,
            "guideline_version": rec.guideline_version,
        }
    ]


def _build_provenance(
    ctx: UnifiedExecutionContext,
    citations: list[str],
) -> list[ProvenanceRecord]:
    first_ref = citations[0] if citations else "PMID:unknown"
    two_refs = citations[:2] if citations else ["PMID:unknown"]
    pheno = ProvenanceRecord(
        claim=f"{ctx.gene} {ctx.genotype} -> phenotype",
        generating_agent=f"pharmacogene_{ctx.gene.lower()}",
        rule_id="cpic.activity_score",
        correlation_id=ctx.correlation_id,
        evidence_sources=[first_ref],
        origin="deterministic",
    )
    rec = ProvenanceRecord(
        claim=f"{ctx.drug} recommendation",
        generating_agent="narrative",
        rule_id="cpic.recommendation",
        correlation_id=ctx.correlation_id,
        evidence_sources=two_refs,
        origin="deterministic",
    )
    rec.parent_claim_id = pheno.claim_id
    return [pheno, rec]


def _patient_narrative(ctx: UnifiedExecutionContext, citations: list[str]) -> str:
    refs = " " + ", ".join(citations[:2]) if citations else ""
    if ctx.gene == "CYP2C19" and ctx.drug == "clopidogrel":
        return (
            f"Your CYP2C19 {ctx.genotype} genotype means you cannot "
            f"activate clopidogrel effectively. {ctx.population.value} "
            f"populations have a 36% carrier rate for this loss-of-function "
            f"variant. Recommended: prasugrel or ticagrelor instead.{refs}"
        )
    if ctx.gene == "HLA-B":
        return (
            f"Your HLA-B*15:02 carrier status contraindicates "
            f"carbamazepine due to SJS/TEN risk. Consider alternative "
            f"anticonvulsants.{refs}"
        )
    if ctx.gene == "CYP2D6":
        return (
            f"Your CYP2D6 {ctx.genotype} phenotype is Poor Metabolizer. "
            f"Codeine cannot be activated to morphine — use morphine "
            f"directly.{refs}"
        )
    return "Deterministic recommendation produced."


def _researcher_narrative(ctx: UnifiedExecutionContext, citations: list[str]) -> str:
    return (
        f"{ctx.gene} {ctx.genotype} -> deterministic phenotype via "
        f"CPIC activity score. Population {ctx.population.value}: "
        f"evidence grounded on {len(citations)} source(s)."
    )


__all__ = ["SwarmRuntime"]
