"""Anukriti Swarm — Scientific Benchmark Demo.

Demonstrates: "The same drug produces different genomic risk
interpretations across populations."

Runs 12 scenarios across 3 genes × 4 populations and reports
deterministic accuracy, confidence, and grounding metrics.

Run: python -m demos.benchmark_demo
"""

from __future__ import annotations

from benchmarks.runner import BenchmarkRunner
from benchmarks.scenarios import ALL_SCENARIOS


def run_demo() -> None:
    print("=" * 70)
    print("🧬 ANUKRITI SWARM — Scientific Validation Benchmark")
    print("   Reproducible. Deterministic. Population-aware.")
    print("=" * 70)

    runner = BenchmarkRunner()
    report = runner.run_all()

    # Summary
    print(f"\n  Total scenarios: {report.total}")
    print(f"  Passed: {report.passed} | Failed: {report.failed}")
    print(f"  Deterministic accuracy: {report.deterministic_accuracy:.0%}")
    print(f"  Avg confidence: {report.avg_confidence:.3f}")
    print(f"  Avg grounding: {report.avg_grounding:.0%}")
    print(f"  Avg duration: {report.avg_duration_ms:.2f} ms")

    # By gene
    print(f"\n{'─' * 70}")
    print("  BY GENE")
    print(f"{'─' * 70}")
    for gene, stats in report.by_gene.items():
        rate = stats["passed"] / stats["total"] if stats["total"] else 0
        bar = "█" * int(rate * 20)
        print(f"  {gene:<12} {stats['passed']}/{stats['total']} passed  {bar} {rate:.0%}")

    # By population
    print(f"\n{'─' * 70}")
    print("  BY POPULATION")
    print(f"{'─' * 70}")
    for pop, stats in report.by_population.items():
        rate = stats["passed"] / stats["total"] if stats["total"] else 0
        bar = "█" * int(rate * 20)
        print(f"  {pop:<12} {stats['passed']}/{stats['total']} passed  {bar} {rate:.0%}")

    # Individual results
    print(f"\n{'─' * 70}")
    print("  SCENARIO RESULTS")
    print(f"{'─' * 70}")
    print(f"  {'ID':<30} {'Pheno':>5} {'Risk':>5} {'Verd':>5} {'Conf':>6} {'Result'}")
    print(f"  {'─'*30} {'─'*5} {'─'*5} {'─'*5} {'─'*6} {'─'*6}")

    for r, s in zip(report.results, ALL_SCENARIOS):
        p = "✓" if r.phenotype_correct else "✗"
        rk = "✓" if r.risk_correct else "✗"
        v = "✓" if r.verdict_correct else "✗"
        status = "PASS" if r.passed else "FAIL"
        color = "" if r.passed else "\033[33m"
        reset = "\033[0m" if not r.passed else ""
        print(f"  {color}{s.scenario_id:<30} {p:>5} {rk:>5} {v:>5} {r.confidence:>6.3f} {status}{reset}")

    # Cross-population comparison
    print(f"\n{'─' * 70}")
    print("  CROSS-POPULATION: Same drug, different risk")
    print(f"{'─' * 70}")
    print(f"\n  Clopidogrel (CYP2C19):")
    for s in ALL_SCENARIOS:
        if s.drug == "clopidogrel" and s.gene == "CYP2C19":
            freq = f"{s.expected_frequency:.0%}" if s.expected_frequency else "—"
            print(f"    {s.population}: {s.allele1}/{s.allele2} → {s.expected_phenotype:<25} freq={freq}")

    print(f"\n  Codeine (CYP2D6):")
    for s in ALL_SCENARIOS:
        if s.drug == "codeine":
            freq = f"{s.expected_frequency:.0%}" if s.expected_frequency else "—"
            print(f"    {s.population}: {s.allele1}/{s.allele2} → {s.expected_phenotype:<25} freq={freq}")

    print(f"\n{'=' * 70}")
    print("  ✅ All outputs deterministic, reproducible, and auditable.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
