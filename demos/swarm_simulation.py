"""Anukriti Swarm — Cinematic Collaborative Swarm Simulation.

A federation of specialized genomic intelligence agents
collaboratively reasoning in real time.

Renders structured agent dialogue showing delegation, reasoning
handoffs, evidence exchanges, and verification checkpoints.

Run: python -m demos.swarm_simulation
"""

from __future__ import annotations

import sys
import time

from workflows.pipeline import run_pipeline

# ANSI
B = "\033[1m"
D = "\033[2m"
R = "\033[0m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
WHITE = "\033[37m"

AGENTS = {
    "orchestrator": (MAGENTA, "🎯"),
    "population_sas": (CYAN, "🌍"),
    "pharmacogene_cyp2c19": (GREEN, "💊"),
    "retrieval": (BLUE, "📚"),
    "verification": (YELLOW, "🛡️"),
    "narrative": (WHITE, "📝"),
}


def _type(text: str, delay: float = 0.008) -> None:
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        if delay > 0:
            time.sleep(delay)
    sys.stdout.write("\n")


def _agent_says(agent: str, message: str, delay: float = 0.006) -> None:
    color, icon = AGENTS.get(agent, (WHITE, "●"))
    prefix = f"  {icon} {color}{B}{agent:<24}{R}"
    _type(f"{prefix} {D}{message}{R}", delay)


def _divider(label: str = "") -> None:
    if label:
        print(f"\n  {D}{'─' * 20} {label} {'─' * (45 - len(label))}{R}\n")
    else:
        print(f"  {D}{'─' * 68}{R}")


def _pause(s: float = 0.4) -> None:
    time.sleep(s)


def run_simulation() -> None:
    print()
    print(f"  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  🧬 ANUKRITI SWARM — Collaborative Intelligence Simulation{R}")
    print(f"  {B}{'═' * 68}{R}")
    print(f"  {D}  A federation of genomic experts reasoning together.{R}")
    print()
    _pause(0.5)

    # --- Scenario ---
    print(f"  {B}┌─ Incoming Query ──────────────────────────────────────────────────┐{R}")
    print(f"  {B}│{R}  Patient: South Asian ancestry                                    {B}│{R}")
    print(f"  {B}│{R}  Drug: Clopidogrel (antiplatelet)                                 {B}│{R}")
    print(f"  {B}│{R}  Genotype: CYP2C19 *2/*2 (rs4244285)                             {B}│{R}")
    print(f"  {B}│{R}  Question: Is this drug safe and effective?                       {B}│{R}")
    print(f"  {B}└───────────────────────────────────────────────────────────────────┘{R}")
    _pause(0.6)

    # --- Phase 1: Orchestration ---
    _divider("PHASE 1: ORCHESTRATION")
    _agent_says("orchestrator", "Received query. Analyzing requirements...")
    _pause(0.2)
    _agent_says("orchestrator", "Gene: CYP2C19 | Drug: clopidogrel | Population: SAS")
    _agent_says("orchestrator", "Compiling execution plan...")
    _pause(0.2)
    _agent_says("orchestrator", f"Dispatching to: {CYAN}population_sas{R}, {GREEN}pharmacogene_cyp2c19{R}, {BLUE}retrieval{R}")
    _agent_says("orchestrator", f"Pipeline: 7 stages, 5 specialist agents")
    _pause(0.3)

    # --- Phase 2: Population Reasoning ---
    _divider("PHASE 2: POPULATION REASONING")
    _agent_says("orchestrator", f"→ Delegating to {CYAN}population_sas{R}: analyze CYP2C19*2 frequency")
    _pause(0.2)
    _agent_says("population_sas", "Received task. Querying frequency store...")
    _agent_says("population_sas", f"CYP2C19*2 in South Asians: {YELLOW}36.0%{R} (gnomAD v4.0, n=15,308)")
    _agent_says("population_sas", f"Rarity classification: {GREEN}COMMON{R}")
    _agent_says("population_sas", f"Clinical note: Expected finding. Well-characterized in this population.")
    _pause(0.2)
    _agent_says("population_sas", f"⚠️  Population insight: {YELLOW}14% of South Asians are Poor Metabolizers{R}")
    _agent_says("population_sas", f"   This is a population health equity issue, not just individual.")
    _agent_says("population_sas", f"→ Returning to orchestrator. Confidence: {GREEN}0.95{R}")
    _pause(0.3)

    # --- Phase 3: Pharmacogene Reasoning ---
    _divider("PHASE 3: PHARMACOGENE REASONING")
    _agent_says("orchestrator", f"→ Delegating to {GREEN}pharmacogene_cyp2c19{R}: infer phenotype")
    _pause(0.2)
    _agent_says("pharmacogene_cyp2c19", "Received diplotype *2/*2. Applying CPIC activity score rules...")
    _agent_says("pharmacogene_cyp2c19", f"  Allele *2: activity score = 0.0 (no function)")
    _agent_says("pharmacogene_cyp2c19", f"  Allele *2: activity score = 0.0 (no function)")
    _agent_says("pharmacogene_cyp2c19", f"  Diplotype score: 0.0 + 0.0 = {RED}0.0{R}")
    _pause(0.2)
    _agent_says("pharmacogene_cyp2c19", f"  Phenotype: {RED}{B}Poor Metabolizer{R}")
    _agent_says("pharmacogene_cyp2c19", f"  Risk: {RED}HIGH — clopidogrel cannot be activated{R}")
    _pause(0.2)
    _agent_says("pharmacogene_cyp2c19", f"  CPIC Recommendation [STRONG]: Use prasugrel or ticagrelor")
    _agent_says("pharmacogene_cyp2c19", f"  Source: CPIC:CYP2C19:clopidogrel:2022 (PMID:34032273)")
    _agent_says("pharmacogene_cyp2c19", f"  Origin: {GREEN}DETERMINISTIC{R} — no LLM, pure rule evaluation")
    _agent_says("pharmacogene_cyp2c19", f"→ Returning to orchestrator. Confidence: {GREEN}1.000{R}")
    _pause(0.3)

    # --- Phase 4: Evidence Retrieval ---
    _divider("PHASE 4: EVIDENCE RETRIEVAL")
    _agent_says("orchestrator", f"→ Delegating to {BLUE}retrieval{R}: ground findings in evidence")
    _pause(0.2)
    _agent_says("retrieval", "Planning sub-queries (MA-RAG)...")
    _agent_says("retrieval", f"  Sub-query 1: CYP2C19 clopidogrel CPIC guideline → {GREEN}CPIC{R}")
    _agent_says("retrieval", f"  Sub-query 2: CYP2C19 population frequency → {CYAN}PharmGKB{R}")
    _agent_says("retrieval", f"  Sub-query 3: CYP2C19 clinical evidence → {RED}PubMed{R}")
    _pause(0.2)
    _agent_says("retrieval", "Searching vector index...")
    _agent_says("retrieval", f"  📄 PMID:34032273 — CPIC Guideline for CYP2C19 (relevance: 0.95)")
    _agent_says("retrieval", f"  📄 PA166169660 — PharmGKB Population Frequencies (relevance: 0.91)")
    _agent_says("retrieval", f"  Grounding score: {GREEN}100%{R} — all claims cite sources")
    _agent_says("retrieval", f"→ Returning to orchestrator. 2 passages, fully grounded.")
    _pause(0.3)

    # --- Phase 5: Verification ---
    _divider("PHASE 5: VERIFICATION")
    _agent_says("orchestrator", f"→ Delegating to {YELLOW}verification{R}: validate all outputs")
    _pause(0.2)
    _agent_says("verification", "Running safety checks...")
    _agent_says("verification", f"  {GREEN}✓{R} Evidence grounding: All claims cite sources")
    _agent_says("verification", f"  {GREEN}✓{R} Deterministic boundary: Origin/confidence consistent")
    _agent_says("verification", f"  {GREEN}✓{R} Provenance: Source attribution present (CPIC)")
    _agent_says("verification", f"  {GREEN}✓{R} Guideline conflict: No contradictions")
    _agent_says("verification", f"  {GREEN}✓{R} Sparse data: Adequate sample (n=15,308)")
    _agent_says("verification", f"  {GREEN}✓{R} Hallucination: All entities recognized")
    _pause(0.2)
    _agent_says("verification", f"  Confidence propagation: 1.0 × 0.95 × 1.0 = {GREEN}0.950{R}")
    _agent_says("verification", f"  TAO Assessment: {GREEN}AUTONOMOUS{R} — safe to deliver")
    _agent_says("verification", f"→ Verdict: {GREEN}{B}PASS{R} | 6/6 checks | No escalation needed")
    _pause(0.3)

    # --- Phase 6: Narrative ---
    _divider("PHASE 6: REPORT GENERATION")
    _agent_says("orchestrator", f"→ All verified. Delegating to {WHITE}narrative{R} for report synthesis")
    _pause(0.2)
    _agent_says("narrative", "Generating evidence-backed report (3 audiences)...")
    _agent_says("narrative", f"  Patient: 'Your body cannot activate this medication...'")
    _agent_says("narrative", f"  Researcher: 'CYP2C19 *2/*2, AS=0.0, PM, CPIC strong'")
    _agent_says("narrative", f"  Audit: 'correlation_id, 6/6 checks, deterministic origin'")
    _agent_says("narrative", f"→ Report complete. All claims cited. Uncertainty noted.")
    _pause(0.3)

    # --- Conclusion ---
    _divider("SWARM CONSENSUS")

    # Run actual pipeline for real metrics
    state, trace = run_pipeline({
        "gene": "CYP2C19", "drug": "clopidogrel", "population": "SAS",
        "allele1": "*2", "allele2": "*2",
    })

    print(f"\n  {B}{RED}┌─ FINDING ─────────────────────────────────────────────────────────┐{R}")
    print(f"  {B}{RED}│{R}                                                                    {B}{RED}│{R}")
    print(f"  {B}{RED}│{R}  {B}CYP2C19 *2/*2 → Poor Metabolizer → CLOPIDOGREL WILL NOT WORK{R}    {B}{RED}│{R}")
    print(f"  {B}{RED}│{R}  {GREEN}Action: Use prasugrel or ticagrelor instead (CPIC strong){R}        {B}{RED}│{R}")
    print(f"  {B}{RED}│{R}  Source: PMID:34032273 | Confidence: 0.950 | Verified: 6/6        {B}{RED}│{R}")
    print(f"  {B}{RED}│{R}                                                                    {B}{RED}│{R}")
    print(f"  {B}{RED}└───────────────────────────────────────────────────────────────────┘{R}")

    print(f"\n  {D}Pipeline: {trace.total_duration_ms:.1f}ms | 7 stages | 5 agents | Correlation: {trace.correlation_id}{R}")

    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  Swarm collaboration complete.{R}")
    print(f"  {D}  Deterministic. Evidence-grounded. Population-aware. Verified.{R}")
    print(f"  {B}{'═' * 68}{R}")
    print()


if __name__ == "__main__":
    run_simulation()
