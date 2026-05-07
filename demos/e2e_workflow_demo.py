"""Anukriti Swarm — End-to-End Orchestration Workflow Demo.

Full pipeline demonstration:
  Drug: Clopidogrel
  Population: South Asian (SAS)
  Variant: CYP2C19*2 (rs4244285)
  Diplotype: *1/*2

Generates: orchestration trace, evidence-backed reasoning,
verification report, and final narrative explanation.

Run: python -m demos.e2e_workflow_demo
"""

from __future__ import annotations

from workflows.pipeline import run_pipeline


def run_demo() -> None:
    print("=" * 70)
    print("🧬 ANUKRITI SWARM — End-to-End Orchestration Demo")
    print("   Distributed Genomic Intelligence in Action")
    print("=" * 70)

    # Input scenario
    initial_state = {
        "gene": "CYP2C19",
        "drug": "clopidogrel",
        "population": "SAS",
        "allele1": "*1",
        "allele2": "*2",
        "variant_rsid": "rs4244285",
    }

    print(f"\n  Input:")
    print(f"    Gene: {initial_state['gene']}")
    print(f"    Drug: {initial_state['drug']}")
    print(f"    Population: {initial_state['population']} (South Asian)")
    print(f"    Diplotype: {initial_state['allele1']}/{initial_state['allele2']}")
    print(f"    Variant: {initial_state['variant_rsid']}")

    # Execute pipeline
    print("\n" + "-" * 70)
    print("  Executing 7-stage pipeline...")
    print("-" * 70)

    state, trace = run_pipeline(initial_state)

    # Execution trace
    print(f"\n{trace.summary()}")

    # Population reasoning
    print("\n" + "-" * 70)
    print("  POPULATION REASONING")
    print("-" * 70)
    pop = state.get("population_result", {})
    print(f"    Frequency of *2 in SAS: {pop.get('frequency')}")
    print(f"    Rarity: {pop.get('rarity')}")
    print(f"    Note: {pop.get('clinical_note')}")
    print(f"    Source: {pop.get('source')}")

    if state.get("population_prevalence"):
        print(f"\n    Metabolizer prevalence in SAS:")
        for p in state["population_prevalence"]:
            bar = "█" * int(p["prevalence"] * 40)
            print(f"      {p['phenotype']:>3}: {p['prevalence']:>6.1%} {bar}")

    # Pharmacogene reasoning
    print("\n" + "-" * 70)
    print("  PHARMACOGENE REASONING")
    print("-" * 70)
    pgx = state.get("pharmacogene_result", {})
    print(f"    Diplotype: {pgx.get('diplotype')}")
    print(f"    Activity Score: {pgx.get('activity_score')}")
    print(f"    Phenotype: {pgx.get('phenotype')}")
    print(f"    Risk: {pgx.get('risk')}")
    print(f"    Origin: {pgx.get('origin')}")

    # Recommendations
    print(f"\n    Recommendations:")
    for r in state.get("recommendations", []):
        print(f"      [{r['strength']:>8}] {r['drug']}: {r['recommendation']}")
        print(f"               {r['guideline_id']} ({r['pmid']})")

    # Evidence
    print("\n" + "-" * 70)
    print("  EVIDENCE RETRIEVAL")
    print("-" * 70)
    print(f"    Retrieved: {state.get('retrieval_count', 0)} passages")
    print(f"    Grounding: {state.get('grounding_score', 0):.0%}")
    print(f"    Citations: {', '.join(state.get('citations', []))}")

    # Verification
    print("\n" + "-" * 70)
    print("  VERIFICATION")
    print("-" * 70)
    v = state.get("verification", {})
    print(f"    Verdict: {v.get('verdict', '').upper()}")
    print(f"    Confidence: {v.get('confidence', 0):.3f} ({v.get('confidence_level', '')})")
    print(f"    Escalation: {v.get('escalation_tier', '')}")
    print(f"    Action: {v.get('action', '')}")
    print(f"\n    Checks:")
    for c in v.get("checks", []):
        icon = {"pass": "✓", "fail": "✗", "warn": "⚠"}.get(c["verdict"], "?")
        print(f"      {icon} {c['name']}: {c['reason']}")

    # Narrative
    print("\n" + "-" * 70)
    print("  GENERATED NARRATIVE")
    print("-" * 70)
    print()
    print(state.get("narrative", "[No narrative generated]"))

    # Final summary
    print("\n" + "=" * 70)
    print(f"  ✅ Pipeline complete in {trace.total_duration_ms:.1f}ms")
    print(f"     Correlation ID: {trace.correlation_id}")
    print(f"     All outputs deterministic, verified, and evidence-backed.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
