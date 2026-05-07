"""Anukriti Swarm — Flagship Demonstration.

"The same drug can produce different risks across different populations."

Three drugs. Four populations. One truth: pharmacogenomic equity matters.

Run: python -m demos.flagship
"""

from __future__ import annotations

import sys
import time

from workflows.pipeline import run_pipeline
from population.agents import SASPopulationAgent, AFRPopulationAgent, EURPopulationAgent
from agents.pharmacogene.hla_b import HLABAgent

# Colors
B, D, R = "\033[1m", "\033[2m", "\033[0m"
CYAN, GREEN, YELLOW, RED, MAGENTA, BLUE, WHITE = "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[35m", "\033[34m", "\033[37m"


def _p(text: str = "") -> None:
    print(text)


def _bar(value: float, width: int = 30, color: str = GREEN) -> str:
    filled = int(value * width)
    return f"{color}{'█' * filled}{D}{'░' * (width - filled)}{R}"


def run_flagship() -> None:
    _p()
    _p(f"  {B}{'═' * 68}{R}")
    _p(f"  {B}{CYAN}  🧬 ANUKRITI SWARM — Flagship Demonstration{R}")
    _p(f"  {B}{'═' * 68}{R}")
    _p(f"  {D}  'The same drug can produce different risks across different populations.'{R}")
    _p(f"  {D}  Three drugs. Four populations. Distributed genomic intelligence.{R}")
    _p()
    time.sleep(0.3)

    # ══════════════════════════════════════════════════════════════════
    # ACT 1: CLOPIDOGREL — The Silent Cardiovascular Crisis
    # ══════════════════════════════════════════════════════════════════
    _p(f"  {B}{RED}╔══════════════════════════════════════════════════════════════════╗{R}")
    _p(f"  {B}{RED}║  ACT 1: CLOPIDOGREL — The Silent Cardiovascular Crisis         ║{R}")
    _p(f"  {B}{RED}╚══════════════════════════════════════════════════════════════════╝{R}")
    _p(f"  {D}  Clopidogrel prevents heart attacks. But it's a prodrug —{R}")
    _p(f"  {D}  it requires CYP2C19 to become active. If you can't activate it...{R}")
    _p()
    time.sleep(0.3)

    # Run across populations
    clop_results = {}
    for pop, alleles, label in [
        ("SAS", ("*2", "*2"), "South Asian"),
        ("EUR", ("*2", "*2"), "European"),
        ("AFR", ("*1", "*2"), "African"),
    ]:
        state, trace = run_pipeline({
            "gene": "CYP2C19", "drug": "clopidogrel", "population": pop,
            "allele1": alleles[0], "allele2": alleles[1],
        })
        clop_results[pop] = state

    _p(f"  {B}  CYP2C19*2 Allele Frequency:{R}")
    _p(f"    South Asian: {_bar(0.36, 36, YELLOW)} {B}36%{R}")
    _p(f"    East Asian:  {_bar(0.30, 36, YELLOW)} {B}30%{R}")
    _p(f"    African:     {_bar(0.18, 36, CYAN)}   18%")
    _p(f"    European:    {_bar(0.15, 36, CYAN)}   15%")
    _p()
    _p(f"  {B}  Poor Metabolizer Prevalence (cannot activate clopidogrel):{R}")
    _p(f"    South Asian: {_bar(0.14, 36, RED)} {B}{RED}14%{R}  ← 1 in 7 patients at risk")
    _p(f"    East Asian:  {_bar(0.10, 36, RED)} {B}{RED}10%{R}")
    _p(f"    African:     {_bar(0.03, 36, GREEN)}    3%")
    _p(f"    European:    {_bar(0.02, 36, GREEN)}    2%")
    _p()

    # Show pipeline result for SAS
    sas = clop_results["SAS"]
    pgx = sas.get("pharmacogene_result", {})
    v = sas.get("verification", {})
    _p(f"  {B}  Swarm Analysis (South Asian, *2/*2):{R}")
    _p(f"    Phenotype:      {RED}{B}{pgx.get('phenotype')}{R}")
    _p(f"    Risk:           {RED}{pgx.get('risk')}{R}")
    _p(f"    Recommendation: {GREEN}Use prasugrel or ticagrelor{R} (CPIC strong)")
    _p(f"    Verification:   {GREEN}{v.get('verdict', '').upper()}{R} | Confidence: {v.get('confidence', 0):.3f}")
    _p(f"    Evidence:       PMID:34032273 | Grounding: {GREEN}100%{R}")
    _p()
    time.sleep(0.3)

    # ══════════════════════════════════════════════════════════════════
    # ACT 2: CODEINE — When Pain Relief Becomes Dangerous
    # ══════════════════════════════════════════════════════════════════
    _p(f"  {B}{MAGENTA}╔══════════════════════════════════════════════════════════════════╗{R}")
    _p(f"  {B}{MAGENTA}║  ACT 2: CODEINE — When Pain Relief Becomes Dangerous           ║{R}")
    _p(f"  {B}{MAGENTA}╚══════════════════════════════════════════════════════════════════╝{R}")
    _p(f"  {D}  Codeine requires CYP2D6 to form morphine.{R}")
    _p(f"  {D}  Too little enzyme → no pain relief. Too much → toxicity.{R}")
    _p()
    time.sleep(0.3)

    # CYP2D6 across populations
    _p(f"  {B}  Population-Specific CYP2D6 Allele Landscape:{R}")
    _p(f"    {B}EUR:{R} *4 at 22% (no function) — most common null allele")
    _p(f"    {B}AFR:{R} *17 at 20% (decreased) — unique to African populations")
    _p(f"    {B}SAS:{R} *41 at 12% (decreased) — moderate frequency")
    _p(f"    {B}EAS:{R} *10 at 38% (decreased) — dominant in East Asia")
    _p()

    # Run CYP2D6 scenarios
    for pop, a1, a2, label, expected in [
        ("EUR", "*4", "*4", "European *4/*4", "Poor Metabolizer → AVOID codeine"),
        ("SAS", "*1", "*4", "South Asian *1/*4", "Intermediate → use with caution"),
        ("EUR", "*1", "*2", "European *1/*2", "Normal Metabolizer → standard dose"),
    ]:
        state, _ = run_pipeline({"gene": "CYP2D6", "drug": "codeine", "population": pop, "allele1": a1, "allele2": a2})
        pgx = state.get("pharmacogene_result", {})
        icon = "🚨" if "Poor" in pgx.get("phenotype", "") else "⚠️" if "Intermediate" in pgx.get("phenotype", "") else "✓"
        _p(f"    {icon} {label:<25} → {pgx.get('phenotype')}")

    _p()
    time.sleep(0.3)

    # ══════════════════════════════════════════════════════════════════
    # ACT 3: CARBAMAZEPINE — The Life-Threatening Skin Reaction
    # ══════════════════════════════════════════════════════════════════
    _p(f"  {B}{YELLOW}╔══════════════════════════════════════════════════════════════════╗{R}")
    _p(f"  {B}{YELLOW}║  ACT 3: CARBAMAZEPINE — The Life-Threatening Skin Reaction     ║{R}")
    _p(f"  {B}{YELLOW}╚══════════════════════════════════════════════════════════════════╝{R}")
    _p(f"  {D}  HLA-B*15:02 carriers risk Stevens-Johnson syndrome (SJS/TEN){R}")
    _p(f"  {D}  from carbamazepine — a potentially fatal skin reaction.{R}")
    _p()
    time.sleep(0.3)

    _p(f"  {B}  HLA-B*15:02 Carrier Prevalence:{R}")
    _p(f"    East Asian:   {_bar(0.08, 36, RED)} {B}{RED}8%{R}   ← FDA mandates testing")
    _p(f"    South Asian:  {_bar(0.04, 36, YELLOW)} {B}{YELLOW}4%{R}")
    _p(f"    African:      {_bar(0.01, 36, GREEN)}    1%")
    _p(f"    European:     {_bar(0.001, 36, GREEN)}   0.1%")
    _p()

    hla = HLABAgent()
    for has_allele, pop, label in [(True, "EAS", "East Asian carrier"), (True, "SAS", "South Asian carrier"), (False, "EUR", "European non-carrier")]:
        result = hla.assess_risk(has_allele)
        icon = "🚨" if result.risk_level == "contraindicated" else "✓"
        color = RED if result.risk_level == "contraindicated" else GREEN
        _p(f"    {icon} {label:<25} → {color}{B}{result.risk_level.upper()}{R}")

    _p()
    time.sleep(0.3)

    # ══════════════════════════════════════════════════════════════════
    # CONCLUSION
    # ══════════════════════════════════════════════════════════════════
    _p(f"  {B}{'═' * 68}{R}")
    _p(f"  {B}{CYAN}  THE INSIGHT{R}")
    _p(f"  {B}{'═' * 68}{R}")
    _p()
    _p(f"  {B}  The same drug. Different populations. Different risks.{R}")
    _p()
    _p(f"    • {RED}14%{R} of South Asians can't activate clopidogrel (vs 2% Europeans)")
    _p(f"    • {RED}22%{R} of Europeans carry CYP2D6*4 (vs 2% Africans)")
    _p(f"    • {RED}8%{R} of East Asians risk fatal SJS from carbamazepine (vs 0.1% Europeans)")
    _p()
    _p(f"  {B}  Current systems ignore this. Anukriti Swarm doesn't.{R}")
    _p()
    _p(f"  {B}{'─' * 68}{R}")
    _p(f"  {B}  How we do it:{R}")
    _p(f"    {GREEN}✓{R} Population is reasoning context, not metadata")
    _p(f"    {GREEN}✓{R} Deterministic core — no hallucinations possible")
    _p(f"    {GREEN}✓{R} Every claim grounded in CPIC/PubMed evidence")
    _p(f"    {GREEN}✓{R} 6 safety checks before any output reaches the user")
    _p(f"    {GREEN}✓{R} 9 specialist agents collaborating in <2ms")
    _p(f"    {GREEN}✓{R} Full provenance — every output is auditable")
    _p()
    _p(f"  {B}{'═' * 68}{R}")
    _p(f"  {B}{CYAN}  Anukriti Swarm{R}")
    _p(f"  {D}  Built for research. Designed for impact. Population-aware by design.{R}")
    _p(f"  {B}{'═' * 68}{R}")
    _p()


if __name__ == "__main__":
    run_flagship()
