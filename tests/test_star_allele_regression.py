"""Pinned regression tests for star-allele → phenotype calls.

Purpose
-------
The deterministic phenotype rules in ``rules/phenotype_rules.py`` are
pinned to specific CPIC table versions. If a future CPIC revision
changes an allele's activity score or shifts a diplotype's phenotype
band, this test must fail *loudly* so the change is reviewed against
the authoritative guideline rather than silently absorbed.

Each assertion below cites the table / revision it is pinned to. When
CPIC publishes a new version, update both the rule table AND the
citation here in the same commit.

Why standalone (not pytest)
---------------------------
The project's verification convention is per-commit smoke tests, not
a pytest suite (``tests/`` was empty as of session #6). This module
runs standalone via ``python -m tests.test_star_allele_regression``
and exits non-zero on any failure.

Run
---
    cd anukriti-swarm
    source venv/bin/activate
    python -m tests.test_star_allele_regression
"""

from __future__ import annotations

import sys

from rules.phenotype_rules import infer_phenotype

# ---------------------------------------------------------------------------
# Pinned case table
# ---------------------------------------------------------------------------
# Each entry: (gene, allele1, allele2, expected_phenotype, citation).
# ``citation`` names the exact CPIC table / guideline version the call
# is pinned to so a future CPIC revision is a visible diff.

PINNED_CASES: list[tuple[str, str, str, str, str]] = [
    # --- CYP2C19 diplotype-to-phenotype (CPIC 2022 clopidogrel
    #     guideline, Lee et al. PMID:35034351; NCBI NBK84114 Table 2)
    ("CYP2C19", "*1", "*1", "Normal Metabolizer", "CPIC 2022 clopidogrel guideline Table 2"),
    (
        "CYP2C19",
        "*1",
        "*17",
        "Rapid Metabolizer",
        "CPIC 2022 clopidogrel guideline Table 2 (*1/*17 -> RM, not NM)",
    ),
    ("CYP2C19", "*17", "*17", "Ultrarapid Metabolizer", "CPIC 2022 clopidogrel guideline Table 2"),
    ("CYP2C19", "*1", "*2", "Intermediate Metabolizer", "CPIC 2022 clopidogrel guideline Table 2"),
    ("CYP2C19", "*2", "*2", "Poor Metabolizer", "CPIC 2022 clopidogrel guideline Table 2"),
    ("CYP2C19", "*2", "*17", "Intermediate Metabolizer", "CPIC 2022 clopidogrel guideline Table 2"),
    # --- CYP2D6 activity score → phenotype (CPIC 2019 standardization,
    #     Caudle et al. 2020 PMID:31647186; allele functions via CPIC
    #     CYP2D6 allele functionality table)
    ("CYP2D6", "*1", "*1", "Normal Metabolizer", "CPIC 2019 standardization (score 2.0 -> NM)"),
    (
        "CYP2D6",
        "*1",
        "*17",
        "Normal Metabolizer",
        "CPIC 2019 standardization (score 1.5 -> NM, not IM as pre-2019)",
    ),
    (
        "CYP2D6",
        "*1",
        "*4",
        "Intermediate Metabolizer",
        "CPIC 2019 standardization (score 1.0 -> IM)",
    ),
    ("CYP2D6", "*4", "*4", "Poor Metabolizer", "CPIC 2019 standardization (score 0 -> PM)"),
    (
        "CYP2D6",
        "*17",
        "*17",
        "Intermediate Metabolizer",
        "CPIC 2019 standardization (score 1.0 -> IM)",
    ),
    (
        "CYP2D6",
        "*1xN",
        "*1",
        "Ultrarapid Metabolizer",
        "CPIC 2019 standardization (score 3.0 -> UM)",
    ),
]


# ---------------------------------------------------------------------------
# Cross-check: benchmark scenarios agree with the rule for *1/*17 cases
# ---------------------------------------------------------------------------


def _check_benchmark_agreement() -> list[str]:
    """Catch drift between benchmark expected_phenotype and the rule.

    The benchmark sits downstream of the rule — its expected values
    must agree with what ``infer_phenotype`` produces for the same
    alleles. If these ever disagree, fail fast with a clear message.
    """
    from benchmarks.scenarios import ALL_SCENARIOS

    mismatches: list[str] = []
    for s in ALL_SCENARIOS:
        if s.gene == "HLA-B":
            continue  # HLA-B uses binary risk, not activity-score.
        result = infer_phenotype(s.gene, s.allele1, s.allele2)
        if result.phenotype != s.expected_phenotype:
            mismatches.append(
                f"  {s.scenario_id}: rule says {result.phenotype!r} "
                f"but benchmark expects {s.expected_phenotype!r} "
                f"(alleles {s.allele1}/{s.allele2})"
            )
    return mismatches


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main() -> int:
    failures: list[str] = []

    for gene, a1, a2, expected, citation in PINNED_CASES:
        result = infer_phenotype(gene, a1, a2)
        if result.phenotype != expected:
            failures.append(
                f"[{gene} {a1}/{a2}] expected {expected!r} "
                f"got {result.phenotype!r} (score {result.activity_score}) "
                f"| pinned to: {citation}"
            )

    benchmark_mismatches = _check_benchmark_agreement()

    total_pinned = len(PINNED_CASES)
    pinned_pass = total_pinned - len(failures)
    print(f"Pinned CPIC cases:       {pinned_pass}/{total_pinned} pass")
    print(f"Benchmark cross-check:   " f"{'AGREE' if not benchmark_mismatches else 'DRIFT'}")

    if failures:
        print("\nFailed pinned cases:")
        for f in failures:
            print(f"  - {f}")

    if benchmark_mismatches:
        print("\nBenchmark ↔ rule mismatches (scenarios.py):")
        for m in benchmark_mismatches:
            print(m)

    if failures or benchmark_mismatches:
        return 1

    print("\nOK: all pinned cases pass and benchmark scenarios agree " "with the rule.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
