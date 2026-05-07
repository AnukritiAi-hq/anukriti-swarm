"""Anukriti Swarm — Verification and Escalation Demo.

Demonstrates three scenarios:
1. PASS: well-grounded output → autonomous delivery
2. ESCALATION: low confidence + failures → human review
3. SPARSE DATA: missing population data → warnings + review

Run: python -m demos.verification_demo
"""

from __future__ import annotations

from verification.engine import VerificationEngine


def run_demo() -> None:
    print("=" * 70)
    print("🧬 ANUKRITI SWARM — Verification & Escalation Demo")
    print("   Healthcare-grade auditability and safety.")
    print("=" * 70)

    engine = VerificationEngine()

    # --- Scenario 1: PASS (autonomous delivery) ---
    print("\n" + "=" * 70)
    print("SCENARIO 1: Well-grounded CYP2D6 analysis → AUTONOMOUS")
    print("=" * 70)

    output_pass = {
        "agent_id": "pharmacogene_cyp2d6",
        "gene": "CYP2D6",
        "drug": "codeine",
        "origin": "deterministic",
        "confidence": 1.0,
        "source": "CPIC:CYP2D6:codeine:2023",
    }
    claims_pass = [
        {"claim": "CYP2D6 *1/*4 is Intermediate Metabolizer", "citations": ["PMID:32722396"]},
        {"claim": "Reduced codeine efficacy expected", "citations": ["PMID:32722396"]},
    ]
    recommendations_pass = [
        {"drug": "codeine", "recommendation": "Use with caution at lowest effective dose."},
    ]

    report = engine.verify(
        output_pass, claims=claims_pass, recommendations=recommendations_pass,
        stage_confidences={"phenotype": 1.0, "population": 0.95, "evidence": 0.92},
    )

    _print_report("SCENARIO 1", report)

    # --- Scenario 2: ESCALATION (human review needed) ---
    print("\n" + "=" * 70)
    print("SCENARIO 2: Ungrounded claims + low confidence → HUMAN ESCALATION")
    print("=" * 70)

    output_escalate = {
        "agent_id": "pharmacogene_cyp2d6",
        "gene": "CYP2D6",
        "drug": "codeine",
        "origin": "generative",
        "confidence": 0.4,
        "source": "",  # Missing provenance!
    }
    claims_escalate = [
        {"claim": "Novel CYP2D6 interaction detected", "citations": []},  # Ungrounded!
        {"claim": "Consider dose reduction", "citations": ["PMID:32722396"]},
    ]

    report2 = engine.verify(
        output_escalate, claims=claims_escalate,
        stage_confidences={"phenotype": 0.4, "evidence": 0.3, "population": 0.5},
    )

    _print_report("SCENARIO 2", report2)

    # --- Scenario 3: SPARSE DATA (population warnings) ---
    print("\n" + "=" * 70)
    print("SCENARIO 3: Sparse population data → MULTI-AGENT REVIEW")
    print("=" * 70)

    output_sparse = {
        "agent_id": "population_amr",
        "gene": "CYP2D6",
        "origin": "deterministic",
        "confidence": 0.7,
        "source": "gnomAD v4.0",
        "population": "AMR",
        "sample_n": 200,  # Small sample!
        "frequency": 0.05,
    }
    claims_sparse = [
        {"claim": "CYP2D6*4 at 5% in AMR", "citations": ["gnomAD:v4.0"]},
    ]

    report3 = engine.verify(
        output_sparse, claims=claims_sparse,
        stage_confidences={"phenotype": 1.0, "population": 0.60, "evidence": 0.85},
    )

    _print_report("SCENARIO 3", report3)

    # --- Summary ---
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Scenario 1: {report.escalation.tier.value:>20} | Verdict: {report.overall_verdict.value}")
    print(f"  Scenario 2: {report2.escalation.tier.value:>20} | Verdict: {report2.overall_verdict.value}")
    print(f"  Scenario 3: {report3.escalation.tier.value:>20} | Verdict: {report3.overall_verdict.value}")
    print("\n" + "=" * 70)
    print("✅ Every output verified. Unsafe outputs escalated. Audit trail complete.")
    print("=" * 70)


def _print_report(label: str, report) -> None:
    """Print a verification report."""
    print(f"\n  Agent: {report.agent_id} | Gene: {report.gene}")
    print(f"  Overall Verdict: {report.overall_verdict.value.upper()}")
    print(f"  Confidence: {report.confidence.value:.3f} ({report.confidence.level.value})")
    print(f"  Escalation: {report.escalation.tier.value}")
    print(f"  Action: {report.escalation.recommended_action}")
    print(f"\n  Checks ({len(report.checks)}):")
    for c in report.checks:
        icon = {"pass": "✓", "fail": "✗", "warn": "⚠", "skip": "○"}[c.verdict.value]
        print(f"    {icon} [{c.verdict.value:>4}] {c.check_name}: {c.reason}")
    if report.escalation.blocking_checks:
        print(f"\n  Blocking: {', '.join(report.escalation.blocking_checks)}")


if __name__ == "__main__":
    run_demo()
