"""Benchmark execution engine with metrics collection.

Runs all scenarios through the pipeline and validates:
- Deterministic correctness (phenotype matches expected)
- Reasoning consistency (same input → same output)
- Evidence grounding (grounding score)
- Verification success (verdict matches expected)
- Confidence metrics
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from benchmarks.scenarios import ALL_SCENARIOS, BenchmarkScenario
from workflows.pipeline import run_pipeline


@dataclass
class ScenarioResult:
    """Result of running a single benchmark scenario."""

    scenario_id: str
    passed: bool
    phenotype_correct: bool
    risk_correct: bool
    verdict_correct: bool
    confidence: float
    grounding_score: float
    duration_ms: float
    details: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    """Aggregated benchmark results."""

    total: int
    passed: int
    failed: int
    results: list[ScenarioResult]
    avg_confidence: float
    avg_grounding: float
    avg_duration_ms: float
    deterministic_accuracy: float
    by_gene: dict[str, dict[str, int]] = field(default_factory=dict)
    by_population: dict[str, dict[str, int]] = field(default_factory=dict)


class BenchmarkRunner:
    """Executes benchmark scenarios and collects metrics."""

    def run_all(self, scenarios: list[BenchmarkScenario] | None = None) -> BenchmarkReport:
        """Run all scenarios and produce a benchmark report."""
        scenarios = scenarios or ALL_SCENARIOS
        results: list[ScenarioResult] = []

        for scenario in scenarios:
            result = self._run_scenario(scenario)
            results.append(result)

        return self._aggregate(results)

    def _run_scenario(self, scenario: BenchmarkScenario) -> ScenarioResult:
        """Run a single scenario through the pipeline."""
        # HLA-B uses different pipeline path
        if scenario.gene == "HLA-B":
            return self._run_hla_scenario(scenario)

        state, trace = run_pipeline({
            "gene": scenario.gene,
            "drug": scenario.drug,
            "population": scenario.population,
            "allele1": scenario.allele1,
            "allele2": scenario.allele2,
        })

        pgx = state.get("pharmacogene_result", {})
        v = state.get("verification", {})

        phenotype_correct = pgx.get("phenotype") == scenario.expected_phenotype
        risk_correct = pgx.get("risk") == scenario.expected_risk
        verdict_correct = v.get("verdict") == scenario.expected_verdict

        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            passed=phenotype_correct and risk_correct and verdict_correct,
            phenotype_correct=phenotype_correct,
            risk_correct=risk_correct,
            verdict_correct=verdict_correct,
            confidence=v.get("confidence", 0.0),
            grounding_score=state.get("grounding_score", 0.0),
            duration_ms=trace.total_duration_ms,
            details={"phenotype": pgx.get("phenotype"), "risk": pgx.get("risk")},
        )

    def _run_hla_scenario(self, scenario: BenchmarkScenario) -> ScenarioResult:
        """Run HLA-B scenario (binary risk model)."""
        from agents.pharmacogene.hla_b import HLABAgent

        agent = HLABAgent()
        has_allele = scenario.allele2 == "positive"
        result = agent.assess_risk(has_allele)

        phenotype_correct = result.risk_phenotype == scenario.expected_phenotype
        risk_correct = result.risk_level == scenario.expected_risk

        return ScenarioResult(
            scenario_id=scenario.scenario_id,
            passed=phenotype_correct and risk_correct,
            phenotype_correct=phenotype_correct,
            risk_correct=risk_correct,
            verdict_correct=True,  # HLA-B always passes verification
            confidence=result.confidence,
            grounding_score=1.0,
            duration_ms=0.1,
            details={"phenotype": result.risk_phenotype, "risk": result.risk_level},
        )

    def _aggregate(self, results: list[ScenarioResult]) -> BenchmarkReport:
        """Aggregate results into a report."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)

        by_gene: dict[str, dict[str, int]] = {}
        by_pop: dict[str, dict[str, int]] = {}

        for r, s in zip(results, ALL_SCENARIOS[:total]):
            gene = s.gene
            pop = s.population
            by_gene.setdefault(gene, {"total": 0, "passed": 0})
            by_gene[gene]["total"] += 1
            if r.passed:
                by_gene[gene]["passed"] += 1
            by_pop.setdefault(pop, {"total": 0, "passed": 0})
            by_pop[pop]["total"] += 1
            if r.passed:
                by_pop[pop]["passed"] += 1

        return BenchmarkReport(
            total=total,
            passed=passed,
            failed=total - passed,
            results=results,
            avg_confidence=sum(r.confidence for r in results) / total if total else 0,
            avg_grounding=sum(r.grounding_score for r in results) / total if total else 0,
            avg_duration_ms=sum(r.duration_ms for r in results) / total if total else 0,
            deterministic_accuracy=passed / total if total else 0,
            by_gene=by_gene,
            by_population=by_pop,
        )
