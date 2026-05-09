"""Anukriti Swarm — Unified Execution Demo.

Closes phase 1 of the Unified Orchestration + Visualization brief.

The canonical execution flow: one callable, one ``UnifiedExecutionReport``
per scenario, three brief-named scenarios rendered side-by-side so
the population-difference story is visible in a single run.

Lifecycle (phase 1 shipped via direct module composition; phase 2
will replace the body with SwarmRuntime.run() but the demo's output
shape stays identical):

    input validation        (UnifiedExecutionContext.new)
        |
        v
    orchestration           (records activated agents)
        |
        v
    retrieval               (multi-strategy BiomedicalRetriever)
        |
        v
    graph reasoning         (MultiHopReasoner with population-weighted paths)
        |
        v
    sufficiency check       (SufficiencyCheckpoint — phase 6 of session #6)
        |
        v
    provenance + synthesis  (ProvenanceRecord + recommendation)
        |
        v
    UnifiedExecutionReport

Scenarios:
    1. Clopidogrel + CYP2C19 + South Asian
    2. Carbamazepine + HLA-B*15:02 + East Asian
    3. Codeine + CYP2D6 + African ancestry

The three scenarios demonstrate the same platform producing
three different outcomes based on population context — the
canonical "population-aware pharmacogenomic risk analysis"
story.

Run:
    python -m demos.unified_demo
"""

from __future__ import annotations

import time
from typing import Any

from core.evidence_sufficiency import SufficiencyCheckpoint
from core.models.population import SuperPopulation
from core.runtime import UnifiedExecutionContext, UnifiedExecutionReport
from integrations.mcp.provenance import ProvenanceRecord
from knowledge_graph import (
    GraphContextBuilder,
    MultiHopReasoner,
    PopulationGraphIndexer,
)
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


# ---------------------------------------------------------------------------
# ANSI formatting (matches sibling demos)
# ---------------------------------------------------------------------------


B, D, R = "\033[1m", "\033[2m", "\033[0m"
CYAN, GREEN, YELLOW, RED, MAGENTA, BLUE = (
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
    "\033[35m",
    "\033[34m",
)


def _banner(title: str, subtitle: str = "") -> None:
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  {title}{R}")
    print(f"  {B}{'═' * 68}{R}")
    if subtitle:
        print(f"  {D}  {subtitle}{R}")


def _scenario(title: str, subtitle: str = "") -> None:
    print(f"\n  {B}{BLUE}  {title}{R}")
    print(f"  {B}{'─' * 68}{R}")
    if subtitle:
        print(f"  {D}  {subtitle}{R}")


# ---------------------------------------------------------------------------
# Lifecycle — each function mutates the context + records activated agents
# ---------------------------------------------------------------------------


ALL_DOCS = CPIC_DOCUMENTS + PHARMGKB_DOCUMENTS + PUBMED_DOCUMENTS


def _stage_orchestration(ctx: UnifiedExecutionContext) -> None:
    """Record the canonical orchestration trace for this run.

    A full implementation will call the Gemini orchestrator; for
    the phase-1 demo we produce the same shape deterministically.
    """

    ctx.record_agent("orchestrator")
    ctx.orchestration_trace = {
        "steps": [
            {"name": "intake",
             "detail": f"Validated {ctx.gene} {ctx.genotype}"},
            {"name": "dispatch",
             "detail": f"Dispatched to {ctx.population.value} specialists"},
        ],
    }


def _stage_retrieval(
    ctx: UnifiedExecutionContext,
    retriever: PopulationAwareRetriever,
) -> dict[str, Any]:
    """Run the multi-strategy retrieval + selector. Record activated agents."""

    ctx.record_agent("population_aware_retriever")
    query = BiomedicalQuery.new(
        gene=ctx.gene, drug=ctx.drug,
        population=ctx.population, genotype=ctx.genotype,
    )
    pop_result = retriever.retrieve(query)
    dense_result = DenseSemanticRetriever().retrieve(query)

    selector = EvidenceSelector(max_per_source=3, max_total=8)
    merged = selector.select([pop_result, dense_result], query=query)

    citations = [c.citation_id for c in merged.result.citations]
    ctx.evidence_state = {
        "citations": citations,
        "total_retrieved": merged.total_retrieved,
        "strategy": merged.strategy,
    }
    # Return for the sufficiency stage.
    return {
        "merged": merged,
        "citations": citations,
    }


def _stage_graph_reasoning(
    ctx: UnifiedExecutionContext,
    graph,
    indexer: PopulationGraphIndexer,
    reasoner: MultiHopReasoner,
) -> list:
    """Run population-weighted multi-hop reasoning."""

    ctx.record_agent("graph_reasoner")
    # Map input scope to KG start/goal ids using the canonical schema.
    allele_guess = f"allele:{ctx.gene}*{ctx.genotype.split('/')[0].lstrip('*')}"
    drug_id = f"drug:{ctx.drug}"

    start_id = allele_guess if graph.has_node(allele_guess) else None
    if start_id is None:
        # Fallback: phenotype-level start when the allele id doesn't match.
        phen_candidates = [
            n.id for n in graph.nodes() if n.id.startswith(f"phenotype:{ctx.gene}")
        ]
        start_id = phen_candidates[0] if phen_candidates else None

    paths: list = []
    if start_id and graph.has_node(drug_id):
        paths = list(reasoner.find_paths(
            graph, start_id, drug_id,
            target_population=ctx.population, pop_indexer=indexer,
        ))

    ctx.graph_state = {
        "start_id": start_id,
        "goal_id": drug_id,
        "paths": [p.to_dict() for p in paths],
    }
    return paths


def _stage_sufficiency(
    ctx: UnifiedExecutionContext,
    checkpoint: SufficiencyCheckpoint,
    retrieval_bundle: dict[str, Any],
    paths: list,
    indexer: PopulationGraphIndexer,
) -> None:
    """Run the full sufficiency + verification + uncertainty + bias stack."""

    ctx.record_agent("sufficiency_checkpoint")

    # Build the run dict the checkpoint expects (same shape as the
    # existing orchestrator produces).
    allele1, _, allele2 = ctx.genotype.partition("/")
    if not allele2:
        allele1, allele2 = ctx.genotype, "positive"

    run = {
        "gene": ctx.gene, "drug": ctx.drug,
        "population": ctx.population,
        "allele1": allele1 or "*1", "allele2": allele2 or "*1",
        "pharmacogene_result": _phenotype_for(ctx),
        "population_result": _pop_result_for(ctx),
        "recommendations": _recommendations_for(ctx),
    }

    provenance_records = [
        ProvenanceRecord(
            claim=f"{ctx.gene} {ctx.genotype} -> phenotype",
            generating_agent=f"pharmacogene_{ctx.gene.lower()}",
            rule_id="cpic.activity_score",
            correlation_id=ctx.correlation_id,
            evidence_sources=list(retrieval_bundle["citations"][:1]) or ["PMID:unknown"],
            origin="deterministic",
        ),
    ]
    rec = ProvenanceRecord(
        claim=f"{ctx.drug} recommendation",
        generating_agent="narrative",
        rule_id="cpic.recommendation",
        correlation_id=ctx.correlation_id,
        evidence_sources=list(retrieval_bundle["citations"][:2]) or ["PMID:unknown"],
        origin="deterministic",
    )
    rec.parent_claim_id = provenance_records[0].claim_id
    provenance_records.append(rec)

    result = checkpoint.evaluate(
        run,
        retrieval_docs=ALL_DOCS,
        provenance_records=provenance_records,
        path_bundle=paths if paths else None,
        pop_indexer=indexer,
        correlation_id=ctx.correlation_id,
    )

    # Persist the full checkpoint result into evidence_state.checkpoint
    # (the UnifiedExecutionReport.from_context extraction key).
    ctx.evidence_state = dict(ctx.evidence_state or {})
    ctx.evidence_state["checkpoint"] = result.to_dict()

    # Verification state carries the rule ids the verifier fired.
    ctx.verification_state = {
        "verdict": result.verdict.verdict.value,
        "rule_ids": [
            result.verdict.rule_id,
            result.report.decision.value,
            result.uncertainty.score.value,
        ],
    }

    # Uncertainty state mirrors the checkpoint uncertainty.
    ctx.uncertainty_state = {
        "score": result.uncertainty.score.value,
        "action": result.uncertainty.action.value,
        "rationale": result.uncertainty.rationale,
    }

    # Provenance state carries the 2 records we just built.
    ctx.provenance_state = {
        "records": [p.to_dict() for p in provenance_records],
    }

    # Record bias-detection agent if any findings.
    if result.bias_findings:
        ctx.record_agent("population_bias_detector")


def _stage_synthesis(ctx: UnifiedExecutionContext) -> None:
    """Deterministic narrative synthesis (no LLM — the demo uses a rule-based writer).

    When the sufficiency checkpoint blocked synthesis, we leave
    narrative_output empty — the report's from_context will build a
    refusal recommendation automatically.
    """

    checkpoint = (ctx.evidence_state or {}).get("checkpoint", {})
    if not checkpoint.get("allows_synthesis"):
        return

    ctx.record_agent("narrative_agent")
    citations = (ctx.evidence_state or {}).get("citations", [])
    ctx.narrative_output = {
        "patient": _patient_narrative(ctx, citations),
        "researcher": _researcher_narrative(ctx, citations),
    }


# ---------------------------------------------------------------------------
# Fixture helpers — canonical deterministic outputs for the 3 scenarios
# ---------------------------------------------------------------------------


def _phenotype_for(ctx: UnifiedExecutionContext) -> dict[str, Any]:
    if ctx.gene == "CYP2C19":
        return {"gene": "CYP2C19", "phenotype": "Poor Metabolizer",
                "rule_id": "cpic.activity_score", "origin": "deterministic"}
    if ctx.gene == "CYP2D6":
        return {"gene": "CYP2D6", "phenotype": "Poor Metabolizer",
                "rule_id": "cpic.activity_score", "origin": "deterministic"}
    if ctx.gene == "HLA-B":
        return {"gene": "HLA-B", "phenotype": "HLA-B*15:02 positive",
                "rule_id": "hla_b.risk_allele", "origin": "deterministic"}
    return {}


def _pop_result_for(ctx: UnifiedExecutionContext) -> dict[str, Any]:
    freqs = {
        ("CYP2C19", SuperPopulation.SAS): 0.36,
        ("CYP2D6", SuperPopulation.AFR): 0.06,
        ("HLA-B", SuperPopulation.EAS): 0.08,
    }
    f = freqs.get((ctx.gene, ctx.population), 0.0)
    if f == 0.0:
        return {}  # forces POPULATION facet into UNCERTAIN/MISSING
    return {"frequency": f, "population": ctx.population.value}


def _recommendations_for(ctx: UnifiedExecutionContext) -> list[dict[str, Any]]:
    table = {
        "clopidogrel": ("Use prasugrel or ticagrelor",
                        ["PMID:34032273", "PA166169660"]),
        "codeine":     ("Avoid codeine; consider morphine directly",
                        ["PMID:32722396"]),
        "carbamazepine": ("Avoid carbamazepine",
                          ["PMID:24407187", "PMID:36123456"]),
    }
    text, refs = table.get(ctx.drug, ("", []))
    return [{"recommendation": text, "evidence_refs": refs}] if text else []


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


# ---------------------------------------------------------------------------
# Unified runner
# ---------------------------------------------------------------------------


def _build_shared_components():
    graph = GraphContextBuilder().build_default()
    indexer = PopulationGraphIndexer.build(graph)
    reasoner = MultiHopReasoner(max_hops=4)
    retriever = PopulationAwareRetriever()
    checkpoint = SufficiencyCheckpoint()
    return graph, indexer, reasoner, retriever, checkpoint


def run_unified(
    *,
    drug: str,
    gene: str,
    population: SuperPopulation | str,
    genotype: str = "unknown",
    question: str = "",
    shared: tuple | None = None,
) -> UnifiedExecutionReport:
    """Run the full unified lifecycle; return a UnifiedExecutionReport."""

    shared = shared or _build_shared_components()
    graph, indexer, reasoner, retriever, checkpoint = shared

    t0 = time.perf_counter()
    ctx = UnifiedExecutionContext.new(
        drug=drug, gene=gene, population=population,
        genotype=genotype, question=question,
    )

    _stage_orchestration(ctx)
    retrieval_bundle = _stage_retrieval(ctx, retriever)
    paths = _stage_graph_reasoning(ctx, graph, indexer, reasoner)
    _stage_sufficiency(ctx, checkpoint, retrieval_bundle, paths, indexer)
    _stage_synthesis(ctx)

    duration_ms = (time.perf_counter() - t0) * 1000
    return UnifiedExecutionReport.from_context(ctx, total_duration_ms=duration_ms)


# ---------------------------------------------------------------------------
# Demo scenarios
# ---------------------------------------------------------------------------


SCENARIOS = [
    {
        "title": "Clopidogrel + CYP2C19 + South Asian",
        "subtitle": "36% SAS carry CYP2C19*2 (loss-of-function) — use prasugrel/ticagrelor.",
        "drug": "clopidogrel", "gene": "CYP2C19",
        "population": SuperPopulation.SAS, "genotype": "*2/*2",
    },
    {
        "title": "Carbamazepine + HLA-B*15:02 + East Asian",
        "subtitle": "HLA-B*15:02 carriers at 8% EAS prevalence — CBZ contraindicated.",
        "drug": "carbamazepine", "gene": "HLA-B",
        "population": SuperPopulation.EAS, "genotype": "*15:02/positive",
    },
    {
        "title": "Codeine + CYP2D6 + African ancestry",
        "subtitle": "CYP2D6*4 PM in AFR — seed lacks AFR-specific evidence.",
        "drug": "codeine", "gene": "CYP2D6",
        "population": SuperPopulation.AFR, "genotype": "*4/*4",
    },
]


def _render(report: UnifiedExecutionReport) -> None:
    rec = report.final_recommendation
    ev = report.evidence_sufficiency or {}
    unc = report.uncertainty_analysis or {}

    gate = f"{GREEN}✓ synthesis{R}" if rec["allows_synthesis"] else f"{RED}✗ refused{R}"
    print(f"  {B}agents:{R} {D}{', '.join(report.activated_agents)}{R}")
    print(f"  {B}graph paths:{R} {len(report.graph_traversal)} · "
          f"{B}deterministic rules:{R} {len(report.deterministic_rules)}")
    print(f"  {B}decision:{R} {ev.get('sufficiency_decision','?')}  "
          f"{B}verdict:{R} {ev.get('verdict','?')}  "
          f"{B}uncertainty:{R} {unc.get('uncertainty_score','?')}  {gate}")
    if rec["allows_synthesis"]:
        print(f"  {B}recommendation:{R} {D}{rec['text'][:72]}{'...' if len(rec['text']) > 72 else ''}{R}")
    else:
        print(f"  {B}blocking:{R} {D}{rec['blocking_reason'][:90]}{R}")
    print(f"  {B}duration:{R} {report.total_duration_ms:.2f}ms")


def main() -> None:
    _banner(
        "🧬 ANUKRITI SWARM — Unified Execution",
        "single lifecycle · 3 scenarios · one UnifiedExecutionReport each"
    )

    shared = _build_shared_components()
    graph, indexer, _, _, _ = shared
    print(f"\n  {D}KG:        {graph.node_count} nodes / {graph.edge_count} edges{R}")
    print(f"  {D}Indexer:   5 super-populations indexed{R}")
    print(f"  {D}Lifecycle: orchestration → retrieval → graph → sufficiency → synthesis{R}")

    reports: list[UnifiedExecutionReport] = []
    for scenario in SCENARIOS:
        _scenario(scenario["title"], scenario["subtitle"])
        report = run_unified(
            drug=scenario["drug"], gene=scenario["gene"],
            population=scenario["population"], genotype=scenario["genotype"],
            shared=shared,
        )
        _render(report)
        reports.append(report)

    # Side-by-side scorecard
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  📋 UNIFIED SCORECARD{R}")
    print(f"  {B}{'═' * 68}{R}")
    print(f"  {B}{'Scenario':42} {'Decision':14} {'Verdict':11} "
          f"{'Uncert.':9} Gate{R}")
    print(f"  {B}{'─' * 100}{R}")
    for sc, rep in zip(SCENARIOS, reports):
        ev = rep.evidence_sufficiency or {}
        unc = rep.uncertainty_analysis or {}
        gate = f"{GREEN}✓{R}" if rep.final_recommendation["allows_synthesis"] else f"{RED}✗{R}"
        print(f"  {sc['title'][:42]:42} "
              f"{ev.get('sufficiency_decision','?')[:14]:14} "
              f"{ev.get('verdict','?')[:11]:11} "
              f"{unc.get('uncertainty_score','?')[:9]:9} {gate}")

    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  Unified orchestration · deterministic core · live-stream ready{R}")
    print(f"  {B}{CYAN}  Evidence-governed genomic intelligence infrastructure.{R}")
    print(f"  {B}{'═' * 68}{R}\n")


if __name__ == "__main__":
    main()
