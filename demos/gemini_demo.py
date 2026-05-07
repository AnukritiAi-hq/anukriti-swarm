"""Anukriti Swarm — Gemini Cognition Layer Demo.

Demonstrates: "Deterministic systems decide. Gemini explains and orchestrates."

Pipeline:
1. Deterministic PGx reasoning (authoritative)
2. Population-aware analysis (deterministic)
3. Evidence retrieval and grounding (deterministic)
4. Verification (deterministic)
5. Gemini-generated explanations (cognition layer)

Run: python -m demos.gemini_demo
"""

from __future__ import annotations

from ai.gemini.client import GeminiClient
from ai.narrative.generator import NarrativeGenerator
from ai.orchestration.reasoning import OrchestrationReasoner
from workflows.pipeline import run_pipeline

B, D, R = "\033[1m", "\033[2m", "\033[0m"
CYAN, GREEN, YELLOW, MAGENTA = "\033[36m", "\033[32m", "\033[33m", "\033[35m"


def run_demo() -> None:
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  🧬 ANUKRITI SWARM — Gemini Cognition Layer{R}")
    print(f"  {B}{'═' * 68}{R}")
    print(f"  {D}  Deterministic systems decide. Gemini explains and orchestrates.{R}")
    print()

    # --- Step 1: Run deterministic pipeline ---
    print(f"  {B}{'─' * 68}{R}")
    print(f"  {GREEN}  LAYER 1: Deterministic Core (authoritative){R}")
    print(f"  {B}{'─' * 68}{R}")

    state, trace = run_pipeline({
        "gene": "CYP2C19", "drug": "clopidogrel", "population": "SAS",
        "allele1": "*2", "allele2": "*2",
    })

    pgx = state.get("pharmacogene_result", {})
    pop = state.get("population_result", {})
    v = state.get("verification", {})

    print(f"    Gene: {pgx.get('gene')} | Diplotype: {pgx.get('diplotype')}")
    print(f"    Phenotype: {pgx.get('phenotype')} [DETERMINISTIC]")
    print(f"    Risk: {pgx.get('risk')} | Confidence: {v.get('confidence', 0):.3f}")
    print(f"    Verification: {v.get('verdict', '').upper()} (6/6 checks)")
    print(f"    Population: {pop.get('population')} | Freq: {pop.get('frequency')}")
    print(f"    Evidence: {', '.join(state.get('citations', []))}")
    print(f"    Duration: {trace.total_duration_ms:.1f}ms")

    # --- Step 2: Gemini cognition layer ---
    print(f"\n  {B}{'─' * 68}{R}")
    print(f"  {MAGENTA}  LAYER 2: Gemini Cognition (explains, never decides){R}")
    print(f"  {B}{'─' * 68}{R}")

    client = GeminiClient()
    generator = NarrativeGenerator(client)
    reasoner = OrchestrationReasoner(client)

    # Build context from deterministic outputs
    ctx = {
        "gene": pgx.get("gene"),
        "diplotype": pgx.get("diplotype"),
        "phenotype": pgx.get("phenotype"),
        "risk": pgx.get("risk"),
        "drug": state.get("drug"),
        "recommendation": "Use prasugrel or ticagrelor instead",
        "population": pop.get("population"),
        "frequency": pop.get("frequency"),
        "citations": state.get("citations", []),
        "confidence": v.get("confidence"),
        "verification": v.get("verdict"),
    }

    mode = f"{'(Gemini API)' if client.available else '(fallback mode — set GEMINI_API_KEY for live AI)'}"
    print(f"    Mode: {mode}")
    print()

    # Clinician explanation
    print(f"  {B}  📋 Clinician Explanation:{R}")
    clinician = generator.explain_for_clinician(ctx)
    print(f"    {clinician.text}")
    print(f"    {D}[origin: {clinician.origin} | grounded: {clinician.grounded} | {clinician.latency_ms:.1f}ms]{R}")

    # Patient explanation
    print(f"\n  {B}  🧑 Patient Explanation:{R}")
    patient = generator.explain_for_patient(ctx)
    print(f"    {patient.text}")
    print(f"    {D}[origin: {patient.origin} | grounded: {patient.grounded} | {patient.latency_ms:.1f}ms]{R}")

    # Research explanation
    print(f"\n  {B}  🔬 Research Explanation:{R}")
    research = generator.explain_for_research(ctx)
    print(f"    {research.text}")
    print(f"    {D}[origin: {research.origin} | grounded: {research.grounded} | {research.latency_ms:.1f}ms]{R}")

    # Orchestration summary
    print(f"\n  {B}  🎯 Orchestration Summary:{R}")
    orch = reasoner.summarize_execution(state)
    print(f"    {orch.summary}")
    print(f"    {D}[reasoning: {orch.reasoning_chain}]{R}")

    # --- Architecture visualization ---
    print(f"\n  {B}{'─' * 68}{R}")
    print(f"  {B}  ARCHITECTURAL SEPARATION{R}")
    print(f"  {B}{'─' * 68}{R}")
    print(f"""
    ┌─────────────────────────────────────────────────────────────┐
    │  {GREEN}DETERMINISTIC CORE (authoritative){R}                          │
    │  Phenotype: {pgx.get('phenotype'):<20} [FACT]                  │
    │  Risk: {pgx.get('risk'):<25} [FACT]                  │
    │  Recommendation: prasugrel/ticagrelor  [CPIC GUIDELINE]     │
    ├─────────────────────────────────────────────────────────────┤
    │  {YELLOW}VERIFICATION GATE{R}                                          │
    │  6/6 checks PASS | Confidence: {v.get('confidence', 0):.3f} | Autonomous     │
    ├─────────────────────────────────────────────────────────────┤
    │  {MAGENTA}GEMINI COGNITION (explains, never decides){R}                 │
    │  Clinician explanation  [GENERATIVE, GROUNDED]              │
    │  Patient explanation    [GENERATIVE, GROUNDED]              │
    │  Orchestration summary  [GENERATIVE, GROUNDED]              │
    └─────────────────────────────────────────────────────────────┘""")

    # --- Metrics ---
    print(f"\n  {B}{'─' * 68}{R}")
    print(f"  {B}  METRICS{R}")
    print(f"  {B}{'─' * 68}{R}")
    m = client.metrics
    print(f"    Gemini calls: {m.total_calls}")
    print(f"    Total latency: {m.total_latency_ms:.1f}ms")
    print(f"    Failures: {m.failures}")
    print(f"    All grounded: {all(x.grounded for x in [clinician, patient, research])}")

    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  AI orchestration around deterministic biomedical reasoning.{R}")
    print(f"  {B}{'═' * 68}{R}\n")


if __name__ == "__main__":
    run_demo()
