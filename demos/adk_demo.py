"""Anukriti Swarm — Google ADK + MongoDB MCP Flagship Demo.

Gemini-powered multi-agent orchestration with deterministic
pharmacogenomic verification and MCP-backed memory infrastructure.

Run: python -m demos.adk_demo
"""

from __future__ import annotations

from integrations.google_adk.orchestrator import ADKOrchestrator

B, D, R = "\033[1m", "\033[2m", "\033[0m"
CYAN, GREEN, YELLOW, RED, MAGENTA = "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[35m"


def run_demo() -> None:
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  🧬 ANUKRITI SWARM — Google ADK + MongoDB MCP Demo{R}")
    print(f"  {B}{'═' * 68}{R}")
    print(f"  {D}  Gemini orchestrates. Deterministic core decides. MCP remembers.{R}")
    print()

    orchestrator = ADKOrchestrator()

    print(f"  {D}  Provider: {orchestrator.ai.provider.value} ({orchestrator.ai.model}){R}")
    print(f"  {D}  MCP Mode: {orchestrator.mcp.mode}{R}")
    print()

    # Execute
    print(f"  {B}  Executing: CYP2C19 *2/*2 + clopidogrel + South Asian{R}")
    print(f"  {B}{'─' * 68}{R}")

    result = orchestrator.execute(
        gene="CYP2C19", drug="clopidogrel", population="SAS",
        allele1="*2", allele2="*2",
    )

    # Steps
    print(f"\n  {B}  Orchestration Steps:{R}")
    for step in result.steps:
        icon = "🔬" if step.origin == "deterministic" else "🤖"
        color = GREEN if step.origin == "deterministic" else MAGENTA
        print(f"    {icon} {color}Step {step.step}: {step.tool:<25}{R} {step.duration_ms:>7.1f}ms  [{step.origin}]")
        if step.tool == "pharmacogene_analysis":
            print(f"       → {step.result.get('phenotype')} | {step.result.get('risk')}")
        elif step.tool == "population_analysis":
            print(f"       → freq={step.result.get('frequency')} | {step.result.get('rarity')}")
        elif step.tool == "verification":
            print(f"       → {step.result.get('verdict')} | conf={step.result.get('confidence', 0):.3f}")

    # Deterministic output
    pgx = result.deterministic_output["pharmacogene"]
    pop = result.deterministic_output["population"]
    ver = result.deterministic_output["verification"]

    print(f"\n  {B}{'─' * 68}{R}")
    print(f"  {GREEN}  DETERMINISTIC CORE (authoritative){R}")
    print(f"  {B}{'─' * 68}{R}")
    print(f"    Phenotype:    {RED}{B}{pgx.get('phenotype')}{R}")
    print(f"    Risk:         {RED}{pgx.get('risk')}{R}")
    print(f"    Activity:     {pgx.get('activity_score')}")
    print(f"    Population:   {pop.get('population')} | freq={pop.get('frequency')} ({pop.get('rarity')})")
    print(f"    Verification: {GREEN}{ver.get('verdict')}{R} | conf={ver.get('confidence', 0):.3f} | {ver.get('escalation_tier')}")
    if pgx.get("recommendations"):
        rec = pgx["recommendations"][0]
        print(f"    CPIC:         [{rec['strength']}] {rec['recommendation']}")
        print(f"                  {rec.get('pmid', '')}")

    # Gemini narrative
    print(f"\n  {B}{'─' * 68}{R}")
    print(f"  {MAGENTA}  GEMINI NARRATIVE (explains, never decides){R}")
    print(f"  {B}{'─' * 68}{R}")
    print(f"\n  {B}  📋 Clinician:{R}")
    print(f"    {result.narrative.get('clinician', 'N/A')}")
    print(f"\n  {B}  🧑 Patient:{R}")
    print(f"    {result.narrative.get('patient', 'N/A')}")

    # MCP stats
    print(f"\n  {B}{'─' * 68}{R}")
    print(f"  {YELLOW}  MONGODB MCP (memory infrastructure){R}")
    print(f"  {B}{'─' * 68}{R}")
    stats = orchestrator.mcp.get_stats()
    print(f"    Mode:       {orchestrator.mcp.mode}")
    print(f"    Traces:     {stats.get('traces', 0)} entries")
    print(f"    Provenance: {stats.get('provenance', 0)} entries")
    print(f"    Memory:     {stats.get('memory', 0)} entries")

    # Summary
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"    Correlation: {result.correlation_id}")
    print(f"    Total time:  {result.total_duration_ms:.0f}ms")
    print(f"    Provider:    {result.gemini_provider}")
    print(f"    MCP:         {result.mcp_mode}")
    print(f"  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  Gemini orchestrates. Core decides. MCP remembers.{R}")
    print(f"  {B}{'═' * 68}{R}\n")


if __name__ == "__main__":
    run_demo()
