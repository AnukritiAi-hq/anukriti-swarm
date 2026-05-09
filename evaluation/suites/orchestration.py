"""``OrchestrationAccuracySuite`` — closes req #2.1.

Validates that the orchestrator + pharmacogene + verification
pipeline produces the expected ``phenotype``, ``risk``, and
``verdict`` for each CPIC scenario.

This is the most fundamental measurement: given a known diplotype,
does the deterministic pipeline yield the phenotype the CPIC
activity-score system prescribes? And does verification accept
that output?

Composes ``benchmarks.runner.BenchmarkRunner`` — re-uses its
12-scenario run loop but emits ``EvaluationResult`` records so the
aggregate ``SwarmEvaluationReport`` (commit 9) can fold this suite
together with the others.

Metrics attached to each result
-------------------------------
    phenotype_correct   bool — observed phenotype == expected
    risk_correct        bool — observed risk == expected
    verdict_correct     bool — verification verdict matches expected
    confidence          float — verification confidence
    grounding_score     float — pipeline's grounding score

Aggregates (on SuiteSummary.aggregates):
    phenotype_accuracy
    risk_accuracy
    verdict_accuracy
    mean_confidence
    mean_grounding
    by_gene    {gene: {'total', 'passed'}}
    by_population
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from benchmarks.runner import BenchmarkRunner
from benchmarks.scenarios import ALL_SCENARIOS, BenchmarkScenario

from evaluation.base import EvaluationCase, EvaluationResult, EvaluationSuite


# ---------------------------------------------------------------------------
# Case adapter
# ---------------------------------------------------------------------------


def cases_from_scenarios(
    scenarios: list[BenchmarkScenario] | None = None,
) -> list[EvaluationCase]:
    """Convert BenchmarkScenario list into EvaluationCase list.

    Kept at module-scope so any suite can reuse the adapter.
    """
    scenarios = scenarios or ALL_SCENARIOS
    out: list[EvaluationCase] = []
    for s in scenarios:
        out.append(
            EvaluationCase(
                case_id=s.scenario_id,
                description=s.description,
                input={
                    "gene": s.gene,
                    "drug": s.drug,
                    "population": s.population,
                    "allele1": s.allele1,
                    "allele2": s.allele2,
                },
                expected={
                    "phenotype": s.expected_phenotype,
                    "risk": s.expected_risk,
                    "verdict": s.expected_verdict,
                    "frequency": s.expected_frequency,
                    "rarity": s.expected_rarity,
                },
                tags=(s.gene.lower(), s.population.lower(), s.drug.lower()),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Suite
# ---------------------------------------------------------------------------


@dataclass
class OrchestrationAccuracySuite(EvaluationSuite):
    """Validates phenotype / risk / verdict correctness per scenario.

    One-shot via ``run(cases_from_scenarios())``. Delegates actual
    pipeline execution to ``BenchmarkRunner`` so this suite stays
    a thin adapter — the runner has HLA-B branching logic that
    would be wasteful to duplicate here.
    """

    name: str = "orchestration_accuracy"
    runner: BenchmarkRunner | None = None

    def __post_init__(self) -> None:
        if self.runner is None:
            self.runner = BenchmarkRunner()
        # Build an index so run_case can look up the source
        # BenchmarkScenario by scenario_id without re-parsing.
        self._scenario_index: dict[str, BenchmarkScenario] = {
            s.scenario_id: s for s in ALL_SCENARIOS
        }

    # ------------------------------------------------------------------
    # Suite contract
    # ------------------------------------------------------------------

    def run_case(self, case: EvaluationCase) -> EvaluationResult:
        scenario = self._scenario_index.get(case.case_id)
        if scenario is None:
            # Case isn't in the canonical scenario set — we can't
            # route it through BenchmarkRunner. Emit a failure with
            # a clear reason.
            return EvaluationResult(
                case_id=case.case_id,
                suite_name=self.name,
                passed=False,
                expected=dict(case.expected),
                reason=(
                    f"case {case.case_id!r} not in benchmarks.ALL_SCENARIOS — "
                    "OrchestrationAccuracySuite only evaluates canonical cases"
                ),
            )

        # BenchmarkRunner has a single-scenario path we reuse.
        scn_result = self.runner._run_scenario(scenario)

        # Compose the pass signal + metrics on the runner result.
        observed = {
            "phenotype": scn_result.details.get("phenotype"),
            "risk": scn_result.details.get("risk"),
            "verdict": "pass" if scn_result.verdict_correct else "fail",
            "confidence": scn_result.confidence,
            "grounding_score": scn_result.grounding_score,
        }
        metrics = {
            "phenotype_correct": scn_result.phenotype_correct,
            "risk_correct": scn_result.risk_correct,
            "verdict_correct": scn_result.verdict_correct,
            "confidence": scn_result.confidence,
            "grounding_score": scn_result.grounding_score,
        }
        # Reason summarizes the mismatch when a case fails.
        if scn_result.passed:
            reason = "phenotype + risk + verdict all match"
        else:
            misses: list[str] = []
            if not scn_result.phenotype_correct:
                misses.append("phenotype")
            if not scn_result.risk_correct:
                misses.append("risk")
            if not scn_result.verdict_correct:
                misses.append("verdict")
            reason = f"mismatch on: {', '.join(misses)}"

        return EvaluationResult(
            case_id=case.case_id,
            suite_name=self.name,
            passed=scn_result.passed,
            observed=observed,
            expected=dict(case.expected),
            metrics=metrics,
            reason=reason,
            duration_ms=scn_result.duration_ms,
            errors=tuple(scn_result.errors),
        )

    def aggregate(self, results: list[EvaluationResult]) -> dict[str, Any]:
        """Compute per-metric accuracy + per-gene / per-pop breakdowns."""
        total = len(results)
        if total == 0:
            return {}

        phen_correct = sum(
            1 for r in results if r.metrics.get("phenotype_correct")
        )
        risk_correct = sum(
            1 for r in results if r.metrics.get("risk_correct")
        )
        verdict_correct = sum(
            1 for r in results if r.metrics.get("verdict_correct")
        )
        sum_conf = sum(float(r.metrics.get("confidence") or 0.0) for r in results)
        sum_ground = sum(
            float(r.metrics.get("grounding_score") or 0.0) for r in results
        )

        by_gene: dict[str, dict[str, int]] = {}
        by_pop: dict[str, dict[str, int]] = {}
        for r in results:
            scn = self._scenario_index.get(r.case_id)
            if scn is None:
                continue
            g = by_gene.setdefault(scn.gene, {"total": 0, "passed": 0})
            g["total"] += 1
            if r.passed:
                g["passed"] += 1
            p = by_pop.setdefault(scn.population, {"total": 0, "passed": 0})
            p["total"] += 1
            if r.passed:
                p["passed"] += 1

        return {
            "phenotype_accuracy": round(phen_correct / total, 4),
            "risk_accuracy": round(risk_correct / total, 4),
            "verdict_accuracy": round(verdict_correct / total, 4),
            "mean_confidence": round(sum_conf / total, 4),
            "mean_grounding": round(sum_ground / total, 4),
            "by_gene": by_gene,
            "by_population": by_pop,
        }


__all__ = ["OrchestrationAccuracySuite", "cases_from_scenarios"]
