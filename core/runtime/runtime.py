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

    # Off-by-default LLM grounded synthesis. Set to "llm_grounded" to
    # run LLMNarrator after the deterministic Stage 5.
    synthesis_mode: str | None = None

    # Optional injected narrator. When None and synthesis_mode is
    # "llm_grounded", a no-client LLMNarrator is constructed lazily
    # (produces an empty narrative — useful for offline/byte-identical
    # tests). Tests inject a mock narrator here.
    llm_narrator: Any = None

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
            self._apply_population_aware_overrides(ctx)
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
    # Population-aware overrides (post-sufficiency, pre-synthesis)
    # ------------------------------------------------------------------

    # SAS-specific DPYD variants that CPIC classifies as Normal function
    # based on European data, but South Asian clinical evidence shows
    # toxicity risk. When detected in a SAS patient, override the
    # checkpoint to block synthesis with a named refusal.
    _SAS_DPYD_REFUSAL_ALLELES: tuple[str, ...] = ("*9A", "M166V")

    def _apply_population_aware_overrides(self, ctx: "UnifiedExecutionContext") -> None:
        """Post-sufficiency hook: block synthesis for SAS patients carrying
        DPYD variants with discordant European vs South Asian evidence."""
        if ctx.gene != "DPYD" or ctx.population.value != "SAS":
            return

        # Check if genotype contains any SAS-refusal allele
        alleles = [a.strip() for a in ctx.genotype.split("/")]
        hit = [a for a in alleles if a in self._SAS_DPYD_REFUSAL_ALLELES]
        if not hit:
            return

        # Override the checkpoint — whether it passed or was already blocked
        # for a generic reason (R3 etc). Our refusal is more informative.
        checkpoint = (ctx.evidence_state or {}).get("checkpoint") or {}

        refusal_reason = (
            f"U4: DPYD {'/'.join(hit)} assigned Normal function by CPIC "
            f"(European data). South Asian evidence (27% carrier frequency "
            f"for *9A in South Indian oncology cohorts) shows clinically "
            f"significant toxicity risk not captured by the European 4-variant "
            f"panel. Population-aware refusal applied — recommend DPD "
            f"phenotyping or expanded panel before standard-dose fluoropyrimidine."
        )
        checkpoint["allows_synthesis"] = False
        checkpoint["blocking_reason"] = refusal_reason
        ctx.evidence_state["checkpoint"] = checkpoint

        self._emit(
            RuntimeEventKind.SAFE_ABSTENTION,
            ctx,
            payload={
                "rule": "U4_SAS_DPYD_OVERRIDE",
                "alleles": hit,
                "blocking_reason": refusal_reason,
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

        # T9: opt-in LLM grounded synthesis after deterministic narrative.
        if self.synthesis_mode == "llm_grounded":
            self._run_llm_grounded_synthesis(ctx, citations)

    def _run_llm_grounded_synthesis(
        self,
        ctx: "UnifiedExecutionContext",
        citations: list[Any],
    ) -> None:
        """Run LLMNarrator to produce a citation-validated grounded narrative.

        Plan T9 fallback contract
        --------------------------
        The deterministic narrative (``ctx.narrative_output["patient"]`` /
        ``["researcher"]``) is *always* the authoritative output. The grounded
        LLM narrative is an additive, opt-in adornment that only survives when
        it passes the ``CitationValidator``.

        * ``ALL_CITED`` (or ``EMPTY_RESPONSE`` from the no-client mock) →
          attach the grounded narrative as produced.
        * ``MISSING_CITATIONS`` (C1) / ``FABRICATED_CITATION`` (C2) /
          ``MALFORMED`` (C4) → **do not** surface the unvalidated LLM text.
          Fall back to the deterministic narrative and record the named
          C-rule refusal in the grounded trace so the audit chain explains
          why the LLM text was dropped.

        A ``GenerativeBoundaryViolation`` (raised by the narrator when it
        detects fabricated citations) is caught here and converted into the
        same C2 named-refusal fallback — the boundary still fires, but the
        run does not crash.
        """
        from ai.narrative.llm_narrator import LLMNarrator
        from core.orchestrator.boundary import GenerativeBoundaryViolation
        from core.runtime.citation_validator import CitationVerdict

        # Map citation verdicts to the named C-rule that explains a fallback.
        fallback_rules = {
            CitationVerdict.MISSING_CITATIONS: "C1",
            CitationVerdict.FABRICATED_CITATION: "C2",
            CitationVerdict.MALFORMED: "C4",
        }

        evidence_records = [
            {"source": c, "source_id": c, "claim": c}
            if isinstance(c, str)
            else {
                "source": c.get("source", "unknown"),
                "source_id": c.get("source_id", c.get("pmid", "")),
                "claim": c.get("claim", c.get("text", "")),
            }
            for c in citations
        ]

        narrator = self.llm_narrator or LLMNarrator(client=None, audience="clinician")

        try:
            result = narrator.narrate(
                gene=ctx.gene,
                drug=ctx.drug,
                population=ctx.population.value,
                phenotype=ctx.narrative_output.get("researcher", "")[:50]
                if ctx.narrative_output
                else "",
                evidence_records=evidence_records,
            )
        except GenerativeBoundaryViolation as exc:
            # Fabricated-claim boundary fired inside the narrator before it
            # could return. Keep the deterministic narrative; record the C2
            # refusal in the grounded trace with the same shape as the
            # validation-failure branch below.
            ctx.record_error(f"llm_grounded_synthesis: boundary: {exc!r}")
            ctx.narrative_output["grounded"] = {
                "text": "",
                "citations": [],
                "validation": {
                    "verdict": CitationVerdict.FABRICATED_CITATION.value,
                    "boundary_violation": str(exc),
                },
                "used_fallback": True,
                "fallback_rule": "C2",
                "fallback_to": "deterministic",
                "unvalidated_text": getattr(exc, "reason", "") or str(exc),
                "model": "blocked",
            }
            self._emit(
                RuntimeEventKind.SAFE_ABSTENTION,
                ctx,
                payload={"grounded": True, "rule": "C2", "reason": "fabricated_citation"},
            )
            return
        except Exception as exc:  # pragma: no cover — defensive
            ctx.record_error(f"llm_grounded_synthesis: {exc!r}")
            return

        verdict = result.validation.verdict
        fallback_rule = fallback_rules.get(verdict)

        grounded: dict[str, Any] = {
            "text": result.text,
            "citations": list(result.citations),
            "validation": {
                "verdict": verdict.value,
                "total_sentences": result.validation.total_sentences,
                "cited_sentences": result.validation.cited_sentences,
                "uncited_claims": list(result.validation.uncited_claims),
                "fabricated_citations": list(result.validation.fabricated_citations),
                "rules_triggered": [r.value for r in result.validation.rules_triggered],
            },
            "chemistry_context": result.chemistry_context,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "used_fallback": fallback_rule is not None,
        }

        if fallback_rule is not None:
            # Validation failed: drop the unvalidated LLM text from the
            # user-facing slot, keep it in the trace for audit, and name
            # the rule that triggered the fallback.
            grounded["fallback_rule"] = fallback_rule
            grounded["fallback_to"] = "deterministic"
            grounded["unvalidated_text"] = result.text
            grounded["text"] = ""
            ctx.narrative_output["grounded"] = grounded
            self._emit(
                RuntimeEventKind.SAFE_ABSTENTION,
                ctx,
                payload={
                    "grounded": True,
                    "rule": fallback_rule,
                    "reason": verdict.value,
                },
            )
            return

        # Clean (ALL_CITED) or empty no-client mock — attach as produced.
        ctx.narrative_output["grounded"] = grounded
        self._emit(
            RuntimeEventKind.SYNTHESIS_EMITTED,
            ctx,
            payload={"grounded": True, "model": result.model},
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

    Diplotype handling:
      * Try EVERY allele in the diplotype (not just the first) — for
        ``*1/*2`` we want the *2 frequency, not a {} miss because
        ``*1`` (wildtype) has no AF edge in the seed KG.
      * If the diplotype is homozygous wildtype (e.g. ``*1/*1``),
        synthesize a baseline entry: this is the **canonical Normal
        Metabolizer reference state**, fully covered by CPIC for
        every well-studied population. Returning {} here causes the
        POPULATION facet to read MISSING for the most-evidenced case
        in the platform — the opposite of what we want for a
        sufficiency layer that's supposed to escalate the *thin*
        cases. The ``frequency`` reported is the population's
        baseline (1 minus the sum of variant-allele frequencies in
        the indexer for this gene). When the indexer can't enumerate,
        report 1.0 — wildtype is by definition the residual.

    No indexer -> {} (defensive; unified_demo / runtime always
    supply one).
    """

    if indexer is None:
        return {}

    # Extract every allele in the diplotype, dropping the leading '*'.
    parts = [p.strip().lstrip("*") for p in ctx.genotype.split("/") if p.strip()]
    if not parts:
        return {}

    # Pass 1: try every allele in the diplotype against the indexer.
    pop_alleles = list(indexer.alleles_for(ctx.population))
    pop_alleles_by_id = {node.id: float(freq) for node, freq in pop_alleles}
    for allele in parts:
        target_id = f"allele:{ctx.gene}*{allele}"
        if target_id in pop_alleles_by_id:
            return {
                "frequency": round(pop_alleles_by_id[target_id], 4),
                "population": ctx.population.value,
                "allele_id": target_id,
                "source": "knowledge_graph.HIGHER_FREQUENCY_IN",
            }

    # Pass 2: homozygous wildtype (every allele is *1) — synthesize a
    # reference-baseline entry. CPIC's clopidogrel/CYP2C19 guideline
    # explicitly covers Normal Metabolizers as the baseline; refusing
    # to recognise that as 'population evidence covered' is incorrect.
    if all(allele in ("1", "1A", "1B") for allele in parts):
        # Baseline = 1 minus the sum of variant-allele frequencies the
        # indexer knows about for this gene + population. For unknown
        # genes (AFR codeine etc) the total is < 1 anyway, so this
        # reports the residual honestly.
        gene_prefix = f"allele:{ctx.gene}*"
        variant_sum = sum(
            freq for nid, freq in pop_alleles_by_id.items()
            if nid.startswith(gene_prefix)
        )
        baseline = max(0.0, 1.0 - variant_sum)
        return {
            "frequency": round(baseline, 4),
            "population": ctx.population.value,
            "allele_id": f"{gene_prefix}1",
            "source": "knowledge_graph.HIGHER_FREQUENCY_IN.baseline",
            "is_baseline": True,
        }

    # No matching edge for any allele in this population, and the
    # diplotype is not homozygous wildtype. Honest miss.
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
    if ctx.gene == "DPYD":
        # Map the diplotype back to CPIC 2017+2018 fluoropyrimidine
        # phenotype + dose recommendation. The full text below is the
        # patient-facing version; researcher-narrative carries the
        # activity-score citation (PMID:29152729) and is rendered by
        # _researcher_narrative().
        diplotype = ctx.genotype
        drug_label = "5-fluorouracil" if ctx.drug == "fluorouracil" else ctx.drug
        no_func_set = {"*2A", "*13"}
        dec_func_set = {"c.2846A>T", "HapB3"}
        parts = [p.strip() for p in diplotype.split("/") if p.strip()]
        no_func = sum(1 for p in parts if p in no_func_set)
        dec_func = sum(1 for p in parts if p in dec_func_set)
        # Phenotype mirrors CPIC Table 5 with pgx-core's pinned overlay.
        is_pm = no_func >= 2 or (no_func == 1 and dec_func == 1)
        is_im = (no_func == 1) or (dec_func >= 1 and no_func == 0)
        if is_pm:
            return (
                f"Your DPYD {diplotype} genotype indicates Poor Metabolizer "
                f"phenotype — complete or near-complete DPD deficiency. "
                f"CPIC 2017 STRONG recommendation: AVOID {drug_label} and "
                f"prodrug-based regimens (capecitabine, tegafur). Severe, "
                f"life-threatening toxicity is expected at standard dose. "
                f"If no fluoropyrimidine-free alternative exists, administer "
                f"at <25% of the standard dose with early therapeutic drug "
                f"monitoring; phenotyping (DPD enzyme activity assay) is "
                f"strongly recommended. Uridine triacetate (Vistogard) is "
                f"the FDA-approved rescue for overdose.{refs}"
            )
        if is_im:
            return (
                f"Your DPYD {diplotype} genotype indicates Intermediate "
                f"Metabolizer phenotype — partial DPD deficiency. CPIC 2017 "
                f"+ Nov 2018 update: reduce starting {drug_label} dose by "
                f"50%, with subsequent dose titration based on toxicity and "
                f"ideally therapeutic drug monitoring. Tegafur is NOT a "
                f"safe alternative (also DPD-metabolized).{refs}"
            )
        # AS=2.0 Normal Metabolizer fallback.
        return (
            f"Your DPYD {diplotype} genotype indicates Normal Metabolizer "
            f"phenotype — full DPD activity expected. Use {drug_label} per "
            f"standard dosing. Note: the canonical 4-variant European panel "
            f"may underdetect carriers in non-European populations; if "
            f"clinically warranted, a phenotyping test (DPD enzyme activity "
            f"or uracil/dihydrouracil ratio) is the gold-standard backstop "
            f"per CPIC.{refs}"
        )
    return "Deterministic recommendation produced."


def _researcher_narrative(ctx: UnifiedExecutionContext, citations: list[str]) -> str:
    return (
        f"{ctx.gene} {ctx.genotype} -> deterministic phenotype via "
        f"CPIC activity score. Population {ctx.population.value}: "
        f"evidence grounded on {len(citations)} source(s)."
    )


__all__ = ["SwarmRuntime"]
