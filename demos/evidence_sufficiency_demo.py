"""Anukriti Swarm — Evidence Sufficiency Layer demo.

Closes requirements #24-25 of the Evidence Sufficiency Layer brief.

Demonstrates the full sufficiency stack end-to-end on the three
brief-named pharmacogenomic scenarios:

    1. Clopidogrel + CYP2C19 + South Asian population
    2. Carbamazepine + HLA-B*15:02 + East Asian population
    3. Codeine + CYP2D6 + African ancestry (sparse population)

Each scenario walks through the same deterministic pipeline:

    coverage analyzer  (6 facets)
        |
        v
    conflict detector  (3 closed classes)
        |
        v
    sufficiency decision engine  (12 rules)
        |
        v
    set-level verifier  (5 verdicts, 10 rules)
        |
        v
    uncertainty scorer  (4 tiers, 9 rules)
        |
        v
    bias detector      (3 closed bias kinds)
        |
        v
    EvidenceSufficiencyTrace
        |
        v
    allows_synthesis  +  blocking_reason

No LLM anywhere. All decisions reproducible run-over-run.
The layer is opt-in — the flagship demos bypass it entirely.

Run:
    python -m demos.evidence_sufficiency_demo
"""

from __future__ import annotations

from core.evidence_sufficiency import (
    ClaimEvidenceFacet,
    FacetCoverageState,
    SufficiencyCheckpoint,
    SufficiencyDecision,
    EvidenceVerdict,
    UncertaintyScore,
    BiasKind,
)
from core.models.population import SuperPopulation
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


# ---------------------------------------------------------------------------
# ANSI formatting (matches safety_demo / interoperability_demo aesthetic)
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


def _facet_color(state: FacetCoverageState) -> str:
    return {
        FacetCoverageState.COVERED: GREEN,
        FacetCoverageState.UNCERTAIN: YELLOW,
        FacetCoverageState.MISSING: RED,
    }[state]


def _decision_color(decision: SufficiencyDecision) -> str:
    if decision in {SufficiencyDecision.SUFFICIENT,
                    SufficiencyDecision.PASS_WITH_CAVEAT}:
        return GREEN
    if decision in {SufficiencyDecision.DOWNGRADE,
                    SufficiencyDecision.REQUEST_MORE,
                    SufficiencyDecision.ESCALATE}:
        return YELLOW
    return RED


def _verdict_color(verdict: EvidenceVerdict) -> str:
    if verdict is EvidenceVerdict.SUPPORTED:
        return GREEN
    if verdict in {EvidenceVerdict.UNCERTAIN, EvidenceVerdict.INSUFFICIENT}:
        return YELLOW
    return RED


def _uncertainty_color(score: UncertaintyScore) -> str:
    return {
        UncertaintyScore.LOW: GREEN,
        UncertaintyScore.MODERATE: YELLOW,
        UncertaintyScore.HIGH: RED,
        UncertaintyScore.UNSAFE: RED,
    }[score]


# ---------------------------------------------------------------------------
# Fixtures — 3 brief-named scenarios (no LLM, all deterministic)
# ---------------------------------------------------------------------------


ALL_DOCS = CPIC_DOCUMENTS + PHARMGKB_DOCUMENTS + PUBMED_DOCUMENTS


def _provenance(correlation_id: str, evidence: tuple[str, ...]) -> list:
    """Build a clean 2-record provenance chain (pharmacogene + narrative)."""

    ref = evidence[0] if evidence else "PMID:unknown"
    recs = [
        ProvenanceRecord(
            claim="phenotype", generating_agent="pharmacogene",
            rule_id="cpic.activity_score", correlation_id=correlation_id,
            evidence_sources=[ref], origin="deterministic",
        ),
        ProvenanceRecord(
            claim="recommendation", generating_agent="narrative",
            rule_id="cpic.recommendation", correlation_id=correlation_id,
            evidence_sources=[ref], origin="deterministic",
        ),
    ]
    recs[1].parent_claim_id = recs[0].claim_id
    return recs


SCENARIOS = [
    {
        "title": "Clopidogrel + CYP2C19 + South Asian",
        "subtitle": "Flagship: 36% SAS carry *2 (loss-of-function) — use prasugrel/ticagrelor.",
        "correlation_id": "ssd-sas-clop",
        "run": {
            "gene": "CYP2C19", "drug": "clopidogrel",
            "population": SuperPopulation.SAS,
            "allele1": "*2", "allele2": "*2",
            "pharmacogene_result": {
                "gene": "CYP2C19", "phenotype": "Poor Metabolizer",
                "rule_id": "cpic.activity_score", "origin": "deterministic",
            },
            "population_result": {"frequency": 0.36, "population": "SAS"},
            "recommendations": [
                {"recommendation": "Use prasugrel or ticagrelor",
                 "evidence_refs": ["PMID:34032273", "PA166169660"]},
            ],
        },
        "evidence": ("PMID:34032273", "PA166169660"),
        "kg_start": "allele:CYP2C19*2",
        "kg_goal": "drug:clopidogrel",
        "target_pop": SuperPopulation.SAS,
    },
    {
        "title": "Carbamazepine + HLA-B*15:02 + East Asian",
        "subtitle": "HLA-B*15:02 carriers at 8% EAS prevalence — CBZ contraindicated.",
        "correlation_id": "ssd-eas-cbz",
        "run": {
            "gene": "HLA-B", "drug": "carbamazepine",
            "population": SuperPopulation.EAS,
            "allele1": "*15:02", "allele2": "positive",
            "pharmacogene_result": {
                "gene": "HLA-B", "phenotype": "HLA-B*15:02 positive",
                "rule_id": "hla_b.risk_allele", "origin": "deterministic",
            },
            "population_result": {"frequency": 0.08, "population": "EAS"},
            "recommendations": [
                {"recommendation": "Avoid carbamazepine",
                 "evidence_refs": ["PMID:24407187", "PMID:36123456"]},
            ],
        },
        "evidence": ("PMID:24407187", "PMID:36123456"),
        "kg_start": "allele:HLA-B*15:02",
        "kg_goal": "drug:carbamazepine",
        "target_pop": SuperPopulation.EAS,
    },
    {
        "title": "Codeine + CYP2D6 + African ancestry",
        "subtitle": "CYP2D6*4 PM in AFR — no AFR-specific population evidence seeds.",
        "correlation_id": "ssd-afr-codeine",
        "run": {
            "gene": "CYP2D6", "drug": "codeine",
            "population": SuperPopulation.AFR,
            "allele1": "*4", "allele2": "*4",
            "pharmacogene_result": {
                "gene": "CYP2D6", "phenotype": "Poor Metabolizer",
                "rule_id": "cpic.activity_score", "origin": "deterministic",
            },
            "population_result": {"frequency": 0.06, "population": "AFR"},
            "recommendations": [
                {"recommendation": "Avoid codeine; use morphine",
                 "evidence_refs": ["PMID:32722396"]},
            ],
        },
        "evidence": ("PMID:32722396",),
        "kg_start": "allele:CYP2D6*4",
        "kg_goal": "drug:codeine",
        "target_pop": SuperPopulation.AFR,
    },
]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_coverage(result) -> None:
    cov = result.report.coverage
    print(f"  {B}Coverage — 6 facets{R}")
    for facet in ClaimEvidenceFacet:
        state = cov.facet_states[facet]
        color = _facet_color(state)
        refs = list(cov.facet_evidence_refs[facet])
        refs_str = (", ".join(refs[:3]) + ("..." if len(refs) > 3 else "")) if refs else "—"
        print(f"    {facet.value:16} {color}{state.value:10}{R}  {D}{refs_str}{R}")
    print(f"  {D}coverage_ratio={cov.coverage_ratio:.4f}"
          f"  missing={[f.value for f in cov.missing_facets]}"
          f"  uncertain={[f.value for f in cov.uncertain_facets]}{R}")


def _render_verdict(result) -> None:
    v = result.verdict
    print(f"  {B}Set-level verdict (SURE-RAG style){R}")
    color = _verdict_color(v.verdict)
    print(f"    {color}{v.verdict.value:14}{R}  {D}{v.rule_id}  {v.rationale}{R}")


def _render_uncertainty(result) -> None:
    u = result.uncertainty
    color = _uncertainty_color(u.score)
    print(f"  {B}Uncertainty tier{R}")
    print(f"    {color}{u.score.value:10}{R}  {D}{u.rule_id}  "
          f"action={u.action.value}  {u.rationale}{R}")


def _render_bias(result) -> None:
    bias = result.bias_findings
    print(f"  {B}Population bias signals{R}")
    if not bias:
        print(f"    {GREEN}none{R}  {D}target population adequately represented{R}")
        return
    for b in bias:
        print(f"    {YELLOW}{b.kind.value:28}{R}  {D}{b.reason}{R}")


def _render_trace(result) -> None:
    t = result.trace
    print(f"  {B}EvidenceSufficiencyTrace{R}")
    print(f"    {D}retrieved_evidence        {list(t.retrieved_evidence)}{R}")
    print(f"    {D}graph_paths               {len(t.graph_paths)} path(s){R}")
    print(f"    {D}missing_hops              {list(t.missing_hops)}{R}")
    print(f"    {D}uncertainty_transitions   {list(t.uncertainty_transitions)}{R}")
    print(f"    {D}sufficiency_decisions     {list(t.sufficiency_decisions)}{R}")
    print(f"    {D}escalation_events         {list(t.escalation_events)}{R}")


def _render_decision(result) -> None:
    d = result.report.decision
    color = _decision_color(d)
    gate = f"{GREEN}allows_synthesis=True{R}" if result.allows_synthesis else f"{RED}allows_synthesis=False{R}"
    print(f"  {B}Sufficiency decision{R}")
    print(f"    {color}{d.value:18}{R}  {D}{result.report.rationale}{R}")
    print(f"    {gate}")
    if not result.allows_synthesis:
        print(f"    {RED}{B}blocking_reason:{R} {D}{result.blocking_reason}{R}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    _banner(
        "🧬 ANUKRITI SWARM — Evidence Sufficiency Layer",
        "3 pharmacogenomic scenarios · deterministic · LLM-free · opt-in"
    )

    # Build shared KG + indexer once; these are idempotent.
    graph = GraphContextBuilder().build_default()
    indexer = PopulationGraphIndexer.build(graph)
    reasoner = MultiHopReasoner(max_hops=4)
    checkpoint = SufficiencyCheckpoint()

    print(f"\n  {D}Knowledge graph:    {graph.node_count} nodes / {graph.edge_count} edges{R}")
    print(f"  {D}Population indexer: 5 super-populations indexed{R}")
    print(f"  {D}Checkpoint stack:   coverage → conflict → sufficiency → "
          f"verdict → uncertainty → bias → trace{R}")

    scorecard: list[tuple[str, str, str, str, str, bool]] = []

    for scenario in SCENARIOS:
        _scenario(f"Scenario — {scenario['title']}", scenario["subtitle"])

        # KG path bundle — population-aware multi-hop
        paths = reasoner.find_paths(
            graph,
            scenario["kg_start"],
            scenario["kg_goal"],
            target_population=scenario["target_pop"],
            pop_indexer=indexer,
        )
        print(f"  {B}KG multi-hop paths{R}")
        print(f"    {len(paths)} path(s) from {scenario['kg_start']} "
              f"-> {scenario['kg_goal']}")
        for p in paths[:2]:
            chain = " -> ".join(n.name for n in p.nodes)
            print(f"    {D}[{p.hop_count}h weight={p.population_weight:.3f}] {chain}{R}")

        result = checkpoint.evaluate(
            scenario["run"],
            retrieval_docs=ALL_DOCS,
            provenance_records=_provenance(
                scenario["correlation_id"], scenario["evidence"]
            ),
            path_bundle=paths,
            pop_indexer=indexer,
            correlation_id=scenario["correlation_id"],
        )

        _render_coverage(result)
        _render_verdict(result)
        _render_uncertainty(result)
        _render_bias(result)
        _render_decision(result)
        _render_trace(result)

        scorecard.append((
            scenario["title"],
            result.report.decision.value,
            result.verdict.verdict.value,
            result.uncertainty.score.value,
            f"{len(result.bias_findings)} bias",
            result.allows_synthesis,
        ))

    # ---------------------------- Scorecard ----------------------------
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  📋 SUFFICIENCY SCORECARD{R}")
    print(f"  {B}{'═' * 68}{R}")
    print(f"  {B}{'Scenario':42} {'Decision':14} {'Verdict':11} "
          f"{'Uncert.':9} {'Bias':10} Gate{R}")
    print(f"  {B}{'─' * 100}{R}")
    for title, decision, verdict, uncertainty, bias_summary, allows in scorecard:
        gate = f"{GREEN}✓{R}" if allows else f"{RED}✗{R}"
        print(f"  {title[:42]:42} {decision[:14]:14} {verdict[:11]:11} "
              f"{uncertainty[:9]:9} {bias_summary[:10]:10} {gate}")

    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  Evidence-governed genomic intelligence infrastructure.{R}")
    print(f"  {B}{CYAN}  Population-aware · Deterministic · Provenance-preserving.{R}")
    print(f"  {B}{'═' * 68}{R}\n")


if __name__ == "__main__":
    main()
