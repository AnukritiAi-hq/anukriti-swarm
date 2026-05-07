"""Anukriti Swarm — Pharmacogene Specialist Agents Demo.

Demonstrates deterministic pharmacogenomic reasoning:
1. CYP2D6 *1/*4 → Intermediate Metabolizer → codeine/tamoxifen recommendations
2. CYP2C19 *2/*2 → Poor Metabolizer → clopidogrel contraindicated
3. HLA-B*15:02 positive → carbamazepine contraindicated

Run: python -m demos.pharmacogene_demo
"""

from __future__ import annotations

from agents.pharmacogene.cyp2d6 import CYP2D6Agent
from agents.pharmacogene.cyp2c19 import CYP2C19Agent
from agents.pharmacogene.hla_b import HLABAgent


def run_demo() -> None:
    print("=" * 70)
    print("🧬 ANUKRITI SWARM — Pharmacogene Specialist Agents Demo")
    print("   Deterministic reasoning. No LLM. Authoritative outputs.")
    print("=" * 70)

    # --- CYP2D6 ---
    print("\n" + "=" * 70)
    print("1. CYP2D6 Agent — Diplotype *1/*4")
    print("=" * 70)

    cyp2d6 = CYP2D6Agent()
    result = cyp2d6.analyze_diplotype("*1", "*4")

    print(f"\n  Agent: {result.agent_id}")
    print(f"  Diplotype: {result.diplotype}")
    print(f"  Activity Score: {result.phenotype_inference.activity_score}")
    print(f"  Phenotype: {result.phenotype_inference.phenotype}")
    print(f"  Risk: {result.risk_classification}")
    print(f"  Confidence: {result.confidence}")
    print(f"  Origin: {result.origin}")
    print(f"\n  Recommendations:")
    for rec in result.recommendations:
        print(f"    [{rec.strength:>8}] {rec.drug}: {rec.recommendation}")
        print(f"             Source: {rec.guideline_id} ({rec.pmid})")
    print(f"\n  Provenance: {result.provenance}")

    # --- CYP2D6 PM ---
    print("\n" + "=" * 70)
    print("2. CYP2D6 Agent — Diplotype *4/*4 (Poor Metabolizer)")
    print("=" * 70)

    result_pm = cyp2d6.analyze_diplotype("*4", "*4")
    print(f"\n  Diplotype: {result_pm.diplotype}")
    print(f"  Activity Score: {result_pm.phenotype_inference.activity_score}")
    print(f"  Phenotype: {result_pm.phenotype_inference.phenotype}")
    print(f"  Risk: {result_pm.risk_classification} ⚠️")
    print(f"\n  Recommendations:")
    for rec in result_pm.recommendations:
        print(f"    [{rec.strength:>8}] {rec.drug}: {rec.recommendation}")

    # --- CYP2C19 ---
    print("\n" + "=" * 70)
    print("3. CYP2C19 Agent — Diplotype *2/*2 (Poor Metabolizer)")
    print("=" * 70)

    cyp2c19 = CYP2C19Agent()
    result_c19 = cyp2c19.analyze_diplotype("*2", "*2")

    print(f"\n  Diplotype: {result_c19.diplotype}")
    print(f"  Activity Score: {result_c19.phenotype_inference.activity_score}")
    print(f"  Phenotype: {result_c19.phenotype_inference.phenotype}")
    print(f"  Risk: {result_c19.risk_classification} ⚠️")
    print(f"\n  Recommendations:")
    for rec in result_c19.recommendations:
        print(f"    [{rec.strength:>8}] {rec.drug}: {rec.recommendation}")
        print(f"             Source: {rec.guideline_id} ({rec.pmid})")

    # --- HLA-B ---
    print("\n" + "=" * 70)
    print("4. HLA-B Agent — *15:02 Positive (SJS/TEN Risk)")
    print("=" * 70)

    hla = HLABAgent()
    risk = hla.assess_risk(has_15_02=True)

    print(f"\n  Status: {risk.allele_status}")
    print(f"  Risk Phenotype: {risk.risk_phenotype}")
    print(f"  Risk Level: {risk.risk_level} 🚨")
    print(f"  Drugs Affected: {', '.join(risk.drugs_affected)}")
    print(f"\n  Recommendations:")
    for rec in risk.recommendations:
        print(f"    [{rec.strength:>8}] {rec.drug}: {rec.recommendation}")

    # --- HLA-B Negative ---
    print("\n" + "-" * 70)
    print("   HLA-B Agent — *15:02 Negative (Safe)")
    print("-" * 70)

    risk_neg = hla.assess_risk(has_15_02=False)
    print(f"  Status: {risk_neg.allele_status}")
    print(f"  Risk Level: {risk_neg.risk_level} ✓")
    print(f"  Drugs Affected: none")

    # --- Summary ---
    print("\n" + "=" * 70)
    print("✅ All analyses deterministic, traceable, and CPIC-aligned.")
    print("   No LLM calls. Pure rule-based reasoning.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
