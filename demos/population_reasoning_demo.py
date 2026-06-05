"""Anukriti Swarm — Population Reasoning Demo.

Demonstrates: "Population is reasoning context, not metadata."

Shows how the same allele (CYP2D6*4) produces fundamentally different
reasoning outputs depending on population context:
- EUR: common, expected, well-characterized
- AFR: rare, unexpected, verify genotyping
- SAS: moderate, standard guidelines apply

Run: python -m demos.population_reasoning_demo
     python -m demos.population_reasoning_demo --real   # gnomAD + SGDP overlay
"""

from __future__ import annotations

import sys

from population.agents import AFRPopulationAgent, EURPopulationAgent, SASPopulationAgent


def run_demo() -> None:
    use_real = "--real" in sys.argv
    freq_kwargs = {"use_gnomad": use_real, "use_sgdp": use_real}

    print("=" * 70)
    print("🧬 ANUKRITI SWARM — Population Reasoning Demo")
    print("   'Population is reasoning context, not metadata.'")
    if use_real:
        print("   ⚡ REAL FREQUENCIES: gnomAD v2.1.1 + SGDP overlay active")
    print("=" * 70)

    agents = [SASPopulationAgent(**freq_kwargs), AFRPopulationAgent(**freq_kwargs), EURPopulationAgent(**freq_kwargs)]

    # --- Demo 1: Same allele, different populations ---
    print("\n" + "=" * 70)
    print("DEMO 1: CYP2D6*4 across populations")
    print("  (Same allele → different clinical significance)")
    print("=" * 70)

    for agent in agents:
        result = agent.reason("CYP2D6", "*4")
        print(f"\n{'─' * 60}")
        print(f"  Population: {agent.population_name} ({agent.population_code})")
        print(f"  Agent: {result.agent_id}")
        print(f"  Frequency: {result.frequency.frequency:.1%}" if result.frequency.found else "  Frequency: N/A")
        print(f"  Rarity: {result.risk_context.rarity_class}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Source: {result.frequency.source} {result.frequency.version}")
        print(f"  Clinical note: {result.risk_context.clinical_note}")
        if result.warnings:
            for w in result.warnings:
                print(f"  ⚠️  WARNING [{w.severity}]: {w.reason}")

    # --- Demo 2: Population-specific allele ---
    print("\n\n" + "=" * 70)
    print("DEMO 2: CYP2D6*17 — African-specific allele")
    print("  (Population determines whether this is expected or surprising)")
    print("=" * 70)

    for agent in agents:
        result = agent.reason("CYP2D6", "*17")
        freq_str = f"{result.frequency.frequency:.1%}" if result.frequency.found and result.frequency.frequency else "0.0%"
        print(f"\n  {agent.population_code}: freq={freq_str:>6} | rarity={result.risk_context.rarity_class:<14} | conf={result.confidence:.2f}")

    # --- Demo 3: Prevalence estimation ---
    print("\n\n" + "=" * 70)
    print("DEMO 3: CYP2C19 metabolizer prevalence by population")
    print("  (Same gene → dramatically different phenotype distributions)")
    print("=" * 70)

    for agent in agents:
        result = agent.reason("CYP2C19", "*2")
        print(f"\n  {agent.population_name} ({agent.population_code}):")
        for est in result.prevalence_estimates:
            bar = "█" * int(est.prevalence * 50)
            print(f"    {est.phenotype:>3}: {est.prevalence:>6.1%} {bar}")
        print(f"    Confidence: {result.prevalence_estimates[0].confidence:.2f} (n={result.prevalence_estimates[0].sample_n:,})")

    # --- Demo 4: Provenance trail ---
    print("\n\n" + "=" * 70)
    print("DEMO 4: Full provenance trail (auditability)")
    print("=" * 70)

    sas = SASPopulationAgent(**freq_kwargs)
    result = sas.reason("CYP2D6", "*4")
    print(f"\n  Query: CYP2D6 *4 in SAS")
    print(f"  Agent ID: {result.agent_id}")
    print(f"  Origin: {result.origin}")
    print(f"  Timestamp: {result.timestamp.isoformat()}")
    print(f"  Frequency source: {result.frequency.source} {result.frequency.version}")
    print(f"  Sample size: n={result.frequency.sample_n:,}")
    print(f"  Risk confidence: {result.risk_context.confidence}")
    print(f"  Prevalence method: {result.prevalence_estimates[0].method}")

    print("\n" + "=" * 70)
    print("✅ Population reasoning demo complete.")
    print("   Every output is deterministic, traceable, and auditable.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
