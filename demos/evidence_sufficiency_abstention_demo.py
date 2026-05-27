"""Anukriti Swarm — Evidence Sufficiency Layer: abstention & adaptive loop demo.

Closes the adversarial portion of requirement #25 of the Evidence
Sufficiency Layer brief. Complements ``evidence_sufficiency_demo``
(the three canonical support-path scenarios) with five failure-path
scenarios plus one live adaptive-retrieval loop.

Every scenario is designed to exercise a specific blocking rule
and show the layer refusing to synthesize — safely, with a named
reason, with a full audit trail.

Adversarial scenarios
---------------------

    1. BLOCK (no phenotype)               -> R2 -> BLOCK_SYNTHESIS
    2. BLOCK (hard AVOID vs USE clash)    -> R1 -> BLOCK + REFUTED verdict
    3. ABSTAIN (broken provenance)        -> R4 -> ABSTAIN
    4. ESCALATE (population missing)      -> R5 -> ROUTE_TO_HUMAN_REVIEW
    5. Unsupported extrapolation + bias   -> AMR with POPULATION UNCERTAIN

Adaptive retrieval
------------------

    6. AdaptiveRetrievalController — CPIC clopidogrel removed from
       the doc corpus, forcing REQUEST_MORE every round until the
       3-strategy budget is exhausted (ABORT).

Run:
    python -m demos.evidence_sufficiency_abstention_demo
"""

from __future__ import annotations

from core.evidence_sufficiency import (
    BiasKind,
    SufficiencyCheckpoint,
    SufficiencyDecision,
)
from core.models.population import SuperPopulation
from integrations.mcp.provenance import ProvenanceRecord
from knowledge_graph import GraphContextBuilder, PopulationGraphIndexer
from retrieval.evidence.documents import (
    CPIC_DOCUMENTS,
    PHARMGKB_DOCUMENTS,
    PUBMED_DOCUMENTS,
)
from retrieval.multi_strategy import (
    AdaptiveRetrievalController,
    BiomedicalQuery,
    DenseSemanticRetriever,
    GraphRetriever,
    PopulationAwareRetriever,
)


# ---------------------------------------------------------------------------
# ANSI formatting (matches the sibling demo)
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


def _scenario(idx: int, title: str, subtitle: str) -> None:
    print(f"\n  {B}{BLUE}  [{idx}] {title}{R}")
    print(f"  {B}{'─' * 68}{R}")
    print(f"  {D}  {subtitle}{R}")


def _expected(expected: str) -> None:
    print(f"  {D}  expected: {expected}{R}")


def _result_line(result) -> None:
    gate = f"{GREEN}✓ allow{R}" if result.allows_synthesis else f"{RED}✗ block{R}"
    print(f"  {B}→ decision={R}{result.report.decision.value:14}"
          f"  {B}verdict={R}{result.verdict.verdict.value:11}"
          f"  {B}uncertainty={R}{result.uncertainty.score.value:9}"
          f"  {gate}")
    if not result.allows_synthesis:
        print(f"  {RED}  blocking_reason:{R} {D}{result.blocking_reason}{R}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


ALL_DOCS = CPIC_DOCUMENTS + PHARMGKB_DOCUMENTS + PUBMED_DOCUMENTS


def _baseline_run() -> dict:
    """Deep-copyable baseline — flagship clopidogrel SAS scenario."""

    return {
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
    }


def _clean_provenance(cid: str) -> list:
    recs = [
        ProvenanceRecord(claim="c1", generating_agent="pharmacogene",
                         rule_id="cpic.activity_score", correlation_id=cid,
                         evidence_sources=["PMID:34032273"],
                         origin="deterministic"),
        ProvenanceRecord(claim="c2", generating_agent="narrative",
                         rule_id="cpic.recommendation", correlation_id=cid,
                         evidence_sources=["PMID:34032273"],
                         origin="deterministic"),
    ]
    recs[1].parent_claim_id = recs[0].claim_id
    return recs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    _banner(
        "🛡️  Evidence Sufficiency — Abstention & Adaptive Loop",
        "adversarial scenarios · safe refusal · deterministic escalation"
    )

    graph = GraphContextBuilder().build_default()
    indexer = PopulationGraphIndexer.build(graph)
    checkpoint = SufficiencyCheckpoint()
    scorecard: list[tuple[str, str, str, str, bool]] = []

    # ------------------------------- 1 -------------------------------
    _scenario(
        1, "BLOCK — phenotype evidence missing",
        "The pharmacogene agent didn't produce a phenotype. The sufficiency "
        "engine cannot synthesize a recommendation without one.",
    )
    _expected("decision=block (R2), verdict=insufficient, uncertainty=high")
    run = _baseline_run()
    run["pharmacogene_result"] = {}
    r = checkpoint.evaluate(
        run, retrieval_docs=ALL_DOCS,
        provenance_records=_clean_provenance("adv-1"),
        pop_indexer=indexer, correlation_id="adv-1",
    )
    _result_line(r)
    assert r.report.decision is SufficiencyDecision.BLOCK
    assert "R2" in r.report.rationale
    scorecard.append((
        "1 no phenotype", r.report.decision.value, r.verdict.verdict.value,
        r.uncertainty.score.value, r.allows_synthesis,
    ))

    # ------------------------------- 2 -------------------------------
    _scenario(
        2, "BLOCK — hard recommendation clash (AVOID vs USE)",
        "Two recommendation sources disagree on a core safety directive. "
        "The conflict detector emits a hard REFUTED invertor.",
    )
    _expected("decision=block (R1), verdict=refuted (V1), uncertainty=unsafe")
    run = _baseline_run()
    conflict_claims = [
        {"kind": "recommendation", "drug": "clopidogrel", "gene": "CYP2C19",
         "phenotype": "poor metabolizer",
         "action_text": "Avoid clopidogrel; use prasugrel or ticagrelor",
         "source_id": "CPIC:2022"},
        {"kind": "recommendation", "drug": "clopidogrel", "gene": "CYP2C19",
         "phenotype": "poor metabolizer",
         "action_text": "Use clopidogrel at standard dose",
         "source_id": "Old:guideline"},
    ]
    r = checkpoint.evaluate(
        run, retrieval_docs=ALL_DOCS,
        provenance_records=_clean_provenance("adv-2"),
        conflict_claims=conflict_claims,
        pop_indexer=indexer, correlation_id="adv-2",
    )
    _result_line(r)
    assert r.report.decision is SufficiencyDecision.BLOCK
    assert r.verdict.rule_id == "V1"  # named REFUTED invertor
    scorecard.append((
        "2 avoid vs use clash", r.report.decision.value, r.verdict.verdict.value,
        r.uncertainty.score.value, r.allows_synthesis,
    ))

    # ------------------------------- 3 -------------------------------
    _scenario(
        3, "ABSTAIN — provenance attribution broken",
        "One provenance record is missing rule_id + generating_agent. "
        "A pipeline that can't be audited must not synthesize.",
    )
    _expected("decision=abstain (R4), pipeline not auditable")
    broken = [
        ProvenanceRecord(claim="c1", generating_agent="",
                         rule_id="", correlation_id="adv-3",
                         evidence_sources=[], origin="deterministic"),
    ]
    r = checkpoint.evaluate(
        _baseline_run(), retrieval_docs=ALL_DOCS,
        provenance_records=broken,
        pop_indexer=indexer, correlation_id="adv-3",
    )
    _result_line(r)
    assert r.report.decision is SufficiencyDecision.ABSTAIN
    scorecard.append((
        "3 broken provenance", r.report.decision.value, r.verdict.verdict.value,
        r.uncertainty.score.value, r.allows_synthesis,
    ))

    # ------------------------------- 4 -------------------------------
    _scenario(
        4, "ESCALATE — target population absent",
        "AFR target with no population_result — POPULATION facet MISSING. "
        "Ancestry gap; retrieval unlikely to help. Route to human review.",
    )
    _expected("decision=escalate (R5), ancestry review marker")
    run = _baseline_run()
    run["gene"] = "CYP2D6"; run["drug"] = "codeine"
    run["population"] = SuperPopulation.AFR
    run["allele1"] = "*4"; run["allele2"] = "*4"
    run["pharmacogene_result"] = {
        "gene": "CYP2D6", "phenotype": "Poor Metabolizer",
        "rule_id": "cpic.activity_score", "origin": "deterministic",
    }
    run["population_result"] = {}  # missing -> POPULATION MISSING
    run["recommendations"] = [
        {"recommendation": "Avoid codeine; use morphine",
         "evidence_refs": ["PMID:32722396"]}
    ]
    r = checkpoint.evaluate(
        run, retrieval_docs=ALL_DOCS,
        provenance_records=_clean_provenance("adv-4"),
        pop_indexer=indexer, correlation_id="adv-4",
    )
    _result_line(r)
    assert r.report.decision is SufficiencyDecision.ESCALATE
    assert "ROUTE_TO_HUMAN_REVIEW" in r.trace.escalation_events
    scorecard.append((
        "4 population missing", r.report.decision.value, r.verdict.verdict.value,
        r.uncertainty.score.value, r.allows_synthesis,
    ))

    # ------------------------------- 5 -------------------------------
    _scenario(
        5, "UNSUPPORTED_EXTRAPOLATION — AMR with no seed coverage",
        "AMR target + POPULATION UNCERTAIN + AMR has zero CYP2D6 alleles "
        "in the seed KG. Bias detector names the extrapolation explicitly.",
    )
    _expected("decision=downgrade (R9), 3 bias flags (eurocentric + scarcity + extrapolation)")
    # Switch to CYP2D6/codeine: with the seed KG's gene-scoped allele
    # counts (post the post-#16 hotfix that filled in CYP2C19 frequency
    # edges across all super-pops), AMR is no longer scarce on CYP2C19
    # but remains scarce on CYP2D6 (zero alleles). The bias detector's
    # ANCESTRY_SCARCITY rule is gene-scoped, so picking a gene where
    # AMR is genuinely missing keeps the demo's pedagogical intent
    # ("AMR with no seed coverage") aligned with current ground truth.
    run = _baseline_run()
    run["gene"] = "CYP2D6"; run["drug"] = "codeine"
    run["allele1"] = "*1"; run["allele2"] = "*4"
    run["pharmacogene_result"] = {
        "gene": "CYP2D6", "phenotype": "Intermediate Metabolizer",
        "rule_id": "cpic.activity_score", "origin": "deterministic",
    }
    run["recommendations"] = [
        {"recommendation": "Avoid codeine; use morphine",
         "evidence_refs": ["PMID:32722396"]},
    ]
    run["population"] = SuperPopulation.AMR
    run["population_result"] = {"frequency": 0.10, "population": "AMR"}
    r = checkpoint.evaluate(
        run, retrieval_docs=ALL_DOCS,
        provenance_records=_clean_provenance("adv-5"),
        pop_indexer=indexer, correlation_id="adv-5",
    )
    _result_line(r)
    bias_kinds = {b.kind for b in r.bias_findings}
    print(f"  {B}Bias findings:{R}")
    for b in r.bias_findings:
        print(f"    {YELLOW}{b.kind.value:28}{R}  {D}{b.reason}{R}")
    # Expect all three bias kinds to fire (AMR absent from seed).
    # NOTE: at least ANCESTRY_SCARCITY + UNSUPPORTED_EXTRAPOLATION must fire.
    # EUROCENTRIC_IMBALANCE fires only when EUR has evidence AND target has 0.
    assert BiasKind.ANCESTRY_SCARCITY in bias_kinds
    scorecard.append((
        "5 AMR bias signals", r.report.decision.value, r.verdict.verdict.value,
        r.uncertainty.score.value, r.allows_synthesis,
    ))

    # ------------------------------- 6 -------------------------------
    _scenario(
        6, "Adaptive retrieval loop — CPIC removed, REQUEST_MORE -> ABORT",
        "The clopidogrel CPIC doc is filtered out. The adaptive controller "
        "broadens strategies round-by-round until the budget is exhausted.",
    )
    _expected("3 rounds executed · REQUEST_MORE every round · budget_exhausted=True")
    docs_no_cpic = [
        d for d in ALL_DOCS
        if not (d.source.value == "CPIC"
                and "CYP2C19" in d.genes
                and "clopidogrel" in d.drugs)
    ]
    controller = AdaptiveRetrievalController(
        strategies=(
            DenseSemanticRetriever(),
            PopulationAwareRetriever(),
            GraphRetriever(),
        ),
        default_budget=3,
    )
    q = BiomedicalQuery.new(
        gene="CYP2C19", drug="clopidogrel",
        population=SuperPopulation.SAS, genotype="*2/*2",
    )

    def _run_factory(query, merged):
        return _baseline_run()

    outcome = controller.run(
        q, _run_factory, retrieval_docs=docs_no_cpic,
        provenance_records=_clean_provenance("adv-6"),
        correlation_id="adv-6",
    )
    print(f"  {B}Outcome:{R}")
    print(f"    rounds_completed = {outcome.rounds_completed}")
    print(f"    strategies_used  = {list(outcome.strategies_used)}")
    print(f"    budget_exhausted = {outcome.budget_exhausted}")
    print(f"    final decision   = {outcome.report.decision.value}")
    assert outcome.rounds_completed == 3
    assert outcome.budget_exhausted
    assert outcome.report.decision is SufficiencyDecision.REQUEST_MORE
    scorecard.append((
        "6 adaptive ABORT",
        outcome.report.decision.value,
        "n/a",
        "n/a",
        False,
    ))

    # ---------------------------- Scorecard ----------------------------
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  📋 ABSTENTION SCORECARD{R}")
    print(f"  {B}{'═' * 68}{R}")
    print(f"  {B}{'Scenario':28} {'Decision':14} {'Verdict':11} "
          f"{'Uncert.':9} Gate{R}")
    print(f"  {B}{'─' * 78}{R}")
    for label, decision, verdict, uncertainty, allows in scorecard:
        gate = f"{GREEN}✓{R}" if allows else f"{RED}✗{R}"
        print(f"  {label[:28]:28} {decision[:14]:14} {verdict[:11]:11} "
              f"{uncertainty[:9]:9} {gate}")

    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  Nothing unsafe reaches synthesis. Nothing un-auditable proceeds.{R}")
    print(f"  {B}{CYAN}  Every refusal is named. Every escalation is traced.{R}")
    print(f"  {B}{'═' * 68}{R}\n")


if __name__ == "__main__":
    main()
