"""Anukriti Swarm — Generic LLM vs Anukriti Deterministic Verified Workflow.

Closes requirement #8 of the evaluation brief and demonstrates
requirement #9's four highlights side-by-side:

  reduced hallucination risk
  stronger provenance
  safer biomedical outputs
  population-aware reasoning advantages

What this demo is
-----------------
A **deterministic** mock of a "generic LLM workflow" — one that
confidently produces biomedical recommendations *without* the
safety engine. No network calls, no actual LLM — just a scripted
generator that reliably hallucinates on the same inputs every
run so the comparison is reproducible.

Run alongside Anukriti's real pipeline on the same four prompts
and print a side-by-side scorecard.

The generic mock is intentionally realistic: it cites plausible
PMIDs, confidently asserts phenotypes, and never blocks anything.
That's the whole point — it models what an ungoverned LLM
agent looks like.

Run:
    python -m demos.comparison_demo
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.orchestrator.gemini_orchestrator import GeminiOrchestrator
from agents.verification import BiomedicalVerificationAgent
from core.verification.escalation_workflow import EscalationWorkflow
from integrations.mcp import MCPClient, MCPPersistenceHook


# ANSI palette (matches the other demos)
B, D, R = "\033[1m", "\033[2m", "\033[0m"
CYAN, GREEN, YELLOW, RED, MAGENTA, BLUE = (
    "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[35m", "\033[34m",
)


def _banner(title: str, subtitle: str = "") -> None:
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  {title}{R}")
    print(f"  {B}{'═' * 68}{R}")
    if subtitle:
        print(f"  {D}  {subtitle}{R}\n")


def _rule(title: str = "", color: str = CYAN) -> None:
    if title:
        print(f"\n  {B}{color}  {title}{R}")
    print(f"  {B}{'─' * 68}{R}")


# ---------------------------------------------------------------------------
# Generic LLM mock
# ---------------------------------------------------------------------------


@dataclass
class GenericLLMResponse:
    """What a generic ungoverned LLM workflow might produce.

    Shaped like the Anukriti OrchestrationResult so the scorecard
    can compare field-for-field, but *not produced by the same
    pipeline* — this is a deterministic mock of a hallucinating
    LLM agent for side-by-side comparison purposes.
    """

    gene: str
    drug: str
    population: str
    phenotype: str
    risk: str
    recommendation: str
    confidence: float
    citations: list[str] = field(default_factory=list)
    is_blocked: bool = False       # generic LLM workflows don't block
    provenance_chain: bool = False  # generic LLMs don't produce chains
    population_aware: bool = False  # generic LLMs ignore population


class GenericLLMWorkflow:
    """Scripted generic-LLM behaviour for 4 canonical scenarios.

    Each scenario produces *confidently wrong* or *under-examined*
    output — the kind of failure mode Anukriti's safety engine is
    designed to catch. Deterministic: same input → same output
    every run so the comparison reproduces.

    Scenarios:

      1. CYP2C19 *2/*2 clopidogrel SAS
         Generic LLM correctly identifies PM but IGNORES the SAS
         population context entirely (same recommendation it would
         give a European patient, same confidence). Missing: the
         2.4× prevalence divergence.

      2. CYP2C19 *1/*1 clopidogrel SAS — PHENOTYPE DRIFT
         Generic LLM confidently asserts 'Poor Metabolizer' for a
         *1/*1 diplotype (which is actually Normal Metabolizer per
         CPIC). Cites a plausible but unrelated PMID.

      3. CYP2D6 *4/*4 codeine EUR
         Generic LLM produces a recommendation but cites only a
         fabricated PMID that doesn't appear in any evidence store.

      4. HLA-B*15:02 carbamazepine EAS — CONFIDENT NO-DATA
         Generic LLM gives a standard-dose recommendation despite
         the positive HLA-B status (which is a CONTRAINDICATION).
         Pure 'confident-on-unknowns' hallucination.
    """

    def run(
        self, *, gene: str, drug: str, population: str,
        allele1: str, allele2: str,
    ) -> GenericLLMResponse:
        # Generic LLM is "confidently wrong": always produces an
        # answer, never blocks, never surfaces uncertainty.

        # Scenario 2 — phenotype drift
        if gene == "CYP2C19" and f"{allele1}/{allele2}" == "*1/*1":
            return GenericLLMResponse(
                gene=gene, drug=drug, population=population,
                phenotype="Poor Metabolizer",  # WRONG — *1/*1 is NM
                risk="high_risk",
                recommendation=(
                    "Avoid clopidogrel; use alternative antiplatelet agent."
                ),
                confidence=0.92,  # confidently wrong
                citations=["PMID:12345678"],  # plausible but unrelated
            )

        # Scenario 3 — fabricated citation
        if gene == "CYP2D6" and allele1 == "*4" and allele2 == "*4":
            return GenericLLMResponse(
                gene=gene, drug=drug, population=population,
                phenotype="Poor Metabolizer",
                risk="high_risk",
                recommendation="Avoid codeine; consider alternative analgesic.",
                confidence=0.89,
                citations=["PMID:99999999"],  # fabricated, not in MCP cache
            )

        # Scenario 4 — HLA-B confident hallucination
        if gene == "HLA-B":
            return GenericLLMResponse(
                gene=gene, drug=drug, population=population,
                phenotype="HLA-B*15:02 positive",
                risk="standard",  # WRONG — *15:02 is a contraindication
                recommendation=(
                    "Carbamazepine can be used at standard starting dose."
                ),
                confidence=0.87,   # confidently wrong
                citations=[],
            )

        # Scenario 1 (default) — correct phenotype, but population-blind
        return GenericLLMResponse(
            gene=gene, drug=drug, population=population,
            phenotype="Poor Metabolizer",
            risk="high_risk",
            recommendation=(
                "Consider alternative antiplatelet agent "
                "(prasugrel or ticagrelor)."
            ),
            confidence=0.85,
            citations=["PMID:34032273"],  # valid for EUR, not SAS-specific
            # population_aware stays False — no SAS-specific prevalence
        )


# ---------------------------------------------------------------------------
# Comparison scenarios
# ---------------------------------------------------------------------------


COMPARISON_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "cyp2c19_sas_correct_phenotype",
        "label": "CYP2C19 *2/*2 + clopidogrel in SAS",
        "why_it_matters": (
            "Both workflows get the phenotype right. Only Anukriti "
            "surfaces the population-specific prevalence (36% in SAS "
            "vs 15% in EUR) — critical for population-level decisions."
        ),
        "gene": "CYP2C19", "drug": "clopidogrel", "population": "SAS",
        "allele1": "*2", "allele2": "*2",
    },
    {
        "id": "cyp2c19_sas_phenotype_drift",
        "label": "CYP2C19 *1/*1 + clopidogrel in SAS (generic LLM DRIFT)",
        "why_it_matters": (
            "*1/*1 is Normal Metabolizer per CPIC. Generic LLM "
            "confidently says Poor Metabolizer → wrong, unsafe "
            "clopidogrel recommendation. Anukriti's phenotype-"
            "correctness check catches the drift and BLOCKS delivery."
        ),
        "gene": "CYP2C19", "drug": "clopidogrel", "population": "SAS",
        "allele1": "*1", "allele2": "*1",
    },
    {
        "id": "cyp2d6_fabricated_pmid",
        "label": "CYP2D6 *4/*4 + codeine + fabricated PMID",
        "why_it_matters": (
            "Generic LLM cites a plausible PMID that doesn't exist in "
            "any evidence store. Anukriti's EvidenceGroundingEngine "
            "flags it as UNRESOLVED and escalates to REQUEST_EVIDENCE."
        ),
        "gene": "CYP2D6", "drug": "codeine", "population": "EUR",
        "allele1": "*4", "allele2": "*4",
    },
]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


@dataclass
class Comparison:
    """Side-by-side outcome for one scenario."""

    scenario_id: str
    label: str
    why: str
    generic: dict[str, Any]
    anukriti: dict[str, Any]


def _score_generic(resp: GenericLLMResponse) -> dict[str, Any]:
    """Compact scorecard for a generic-LLM response."""
    return {
        "phenotype": resp.phenotype,
        "recommendation": resp.recommendation,
        "confidence": resp.confidence,
        "citations": resp.citations,
        "population_aware": resp.population_aware,
        "blocked": resp.is_blocked,
        "provenance_chain": resp.provenance_chain,
        "grounded_in_cache": False,  # generic LLM doesn't check MCP
    }


def _score_anukriti(outcome: Any, plan: Any, run_dict: dict[str, Any]) -> dict[str, Any]:
    """Compact scorecard for an Anukriti VerificationOutcome."""
    pgx = (run_dict.get("pharmacogene_result") or {}) if run_dict else {}
    pop_res = (run_dict.get("population_result") or {}) if run_dict else {}
    recs = run_dict.get("recommendations") or []
    rec_text = recs[0]["recommendation"] if recs else ""
    citations = [
        c if isinstance(c, str) else c.get("source_id", "")
        for c in (run_dict.get("citations") or [])
    ]
    grounding = outcome.grounding
    coverage = grounding.coverage if grounding else 0.0

    return {
        "phenotype": pgx.get("phenotype", ""),
        "recommendation": rec_text,
        "confidence": outcome.decision.score.confidence if outcome.decision else 0.0,
        "citations": citations,
        "population_aware": pop_res.get("frequency") is not None,
        "blocked": bool(outcome.decision and outcome.decision.block),
        "provenance_chain": outcome.provenance is not None and outcome.provenance.records_examined > 0,
        "grounded_in_cache": coverage > 0.5,
        "tier": outcome.tier,
        "grounding_coverage": round(coverage, 2),
        "plan_status": plan.status,
    }


# ---------------------------------------------------------------------------
# Side-by-side renderer
# ---------------------------------------------------------------------------


def _fmt_bool(v: bool, good_when_true: bool = True) -> str:
    """Green check / red x, or yellow dash for None."""
    if v is None:
        return f"{YELLOW}—{R}"
    is_good = bool(v) == good_when_true
    if is_good:
        return f"{GREEN}✓{R}"
    return f"{RED}✗{R}"


def _fmt_table(
    comp: Comparison,
) -> None:
    """Print a 3-column comparison for one scenario."""
    g = comp.generic
    a = comp.anukriti
    col1_w = 26
    col2_w = 20
    col3_w = 20

    rows: list[tuple[str, Any, Any]] = [
        ("phenotype", g["phenotype"], a["phenotype"]),
        ("recommendation",
         (g["recommendation"] or "")[:col2_w - 3] + "...",
         (a["recommendation"] or "")[:col3_w - 3] + "..."),
        ("confidence", f"{g['confidence']:.2f}", f"{a['confidence']:.2f}"),
        ("citations", ", ".join(g["citations"]) or "none",
                      ", ".join(a["citations"]) or "none"),
        ("population_aware",
         _fmt_bool(g["population_aware"]),
         _fmt_bool(a["population_aware"])),
        ("grounded_in_cache",
         _fmt_bool(g["grounded_in_cache"]),
         _fmt_bool(a["grounded_in_cache"])),
        ("provenance_chain",
         _fmt_bool(g["provenance_chain"]),
         _fmt_bool(a["provenance_chain"])),
        ("blocked?",
         _fmt_bool(g["blocked"], good_when_true=False),
         _fmt_bool(a["blocked"], good_when_true=False)),
    ]

    hdr_g = "Generic LLM"
    hdr_a = "Anukriti"
    print(f"  {B}{'':<{col1_w}}{hdr_g:<{col2_w}}{hdr_a:<{col3_w}}{R}")
    print(f"  {B}{'─' * (col1_w + col2_w + col3_w)}{R}")
    for label, gv, av in rows:
        print(f"  {D}{label:<{col1_w}}{R}{str(gv):<{col2_w}}{str(av):<{col3_w}}")

    # Anukriti-only supplementary details.
    print()
    print(f"  {D}  Anukriti tier:              {a['tier']}{R}")
    print(f"  {D}  Anukriti plan status:       {a['plan_status']}{R}")
    print(f"  {D}  Anukriti grounding coverage:{a['grounding_coverage']:.0%}{R}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_demo() -> None:
    _banner(
        "⚔  ANUKRITI SWARM — Comparison: Generic LLM vs Anukriti",
        "Same inputs. Different governance. Different safety outcomes.",
    )

    # ----- Wire Anukriti stack ----------------------------------------
    client = MCPClient()
    orch = GeminiOrchestrator()
    hook = MCPPersistenceHook(client=client)
    agent = BiomedicalVerificationAgent(client=client)
    workflow = EscalationWorkflow()
    generic = GenericLLMWorkflow()

    comparisons: list[Comparison] = []

    for i, scn in enumerate(COMPARISON_SCENARIOS, 1):
        _rule(f"{i}. {scn['label']}", BLUE)
        print(f"  {D}  {scn['why_it_matters']}{R}")
        print()

        # --- Generic LLM run ---
        g_resp = generic.run(
            gene=scn["gene"], drug=scn["drug"], population=scn["population"],
            allele1=scn["allele1"], allele2=scn["allele2"],
        )

        # --- Anukriti run ---
        a_result = orch.run(
            gene=scn["gene"], drug=scn["drug"], population=scn["population"],
            allele1=scn["allele1"], allele2=scn["allele2"],
        )
        hook.persist(a_result)
        run_dict = (
            a_result.coordination.runs[0]
            if a_result.coordination.runs
            else {}
        )
        a_outcome = agent.verify_run(
            run_dict, correlation_id=a_result.context.correlation_id,
        )
        a_plan = workflow.plan(a_outcome)

        comp = Comparison(
            scenario_id=scn["id"],
            label=scn["label"],
            why=scn["why_it_matters"],
            generic=_score_generic(g_resp),
            anukriti=_score_anukriti(a_outcome, a_plan, run_dict),
        )
        comparisons.append(comp)
        _fmt_table(comp)

    # -----------------------------------------------------------------
    # Summary scorecard
    # -----------------------------------------------------------------
    _banner("📊 HIGHLIGHTED DIFFERENCES")

    # Summary counts: what fraction of scenarios each system
    # 'got right' on each dimension. For 'hallucination risk' we
    # count scenarios where the system's output is trustworthy
    # (Anukriti: tier not in {conflicting, unsafe}; Generic: always
    # trusts itself, so always 0 since it has no internal check).
    anukriti_trustworthy = sum(
        1 for c in comparisons
        if c.anukriti["tier"] not in ("conflicting", "unsafe")
    )
    lines = [
        (
            "Internal hallucination check",
            0,   # Generic LLM has no internal hallucination check
            sum(1 for c in comparisons if c.anukriti["provenance_chain"]),
        ),
        (
            "Stronger provenance chain",
            sum(1 for c in comparisons if c.generic["provenance_chain"]),
            sum(1 for c in comparisons if c.anukriti["provenance_chain"]),
        ),
        (
            "Evidence grounded in cache",
            sum(1 for c in comparisons if c.generic["grounded_in_cache"]),
            sum(1 for c in comparisons if c.anukriti["grounded_in_cache"]),
        ),
        (
            "Population-aware reasoning",
            sum(1 for c in comparisons if c.generic["population_aware"]),
            sum(1 for c in comparisons if c.anukriti["population_aware"]),
        ),
        (
            "Auditable safety decisions",
            0,   # Generic LLM has no safety decision signal
            sum(1 for c in comparisons if c.anukriti.get("tier")),
        ),
    ]
    print(f"  {B}{'Metric':<35} {'Generic LLM':<18} {'Anukriti':<18}{R}")
    print(f"  {B}{'─' * 71}{R}")
    for label, g, a in lines:
        g_str = f"{g}/{len(comparisons)}"
        a_str = f"{a}/{len(comparisons)}"
        print(f"  {label:<35} {g_str:<18} {a_str:<18}")

    print(f"\n  {B}{'═' * 68}{R}")
    print(
        f"  {B}{CYAN}  Same pharmacogenomic queries. "
        f"Different safety posture.{R}"
    )
    print(
        f"  {B}{CYAN}  Anukriti: verified, grounded, "
        f"population-aware, auditable.{R}"
    )
    print(f"  {B}{'═' * 68}{R}\n")

    client.close()


if __name__ == "__main__":
    run_demo()
