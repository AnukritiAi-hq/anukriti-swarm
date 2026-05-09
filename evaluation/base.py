"""Evaluation primitives — case, result, suite base.

Three dataclasses + one ABC. Everything else in the package
consumes these. Kept deliberately minimal so every suite can
add suite-specific metrics without mutating the base types.

    EvaluationCase      one input to evaluate
    EvaluationResult    observed outputs + pass/fail + metrics
    SuiteSummary        aggregated metrics for a full suite run
    EvaluationSuite     ABC — subclasses implement run_case()

Design
------
- Cases and results are frozen dataclasses. Once an eval finishes,
  its result is part of the audit trail.
- Every result carries ``metrics: dict[str, Any]`` so suites can
  attach their own bespoke numbers (grounding rate, token usage,
  failure reason) without schema changes.
- The base ``EvaluationSuite`` handles the scaffolding — scenario
  iteration, aggregation, error capture — subclasses only have
  to implement ``run_case(case) -> EvaluationResult``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Primitive records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluationCase:
    """One input to evaluate.

    A case is a thin wrapper around whatever input shape a suite
    needs. Typical use: wrap a ``BenchmarkScenario`` via its
    ``scenario_id`` and store suite-specific expected outputs in
    ``expected``.
    """

    case_id: str
    description: str = ""
    input: dict[str, Any] = field(default_factory=dict)
    expected: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()   # free-form: 'cyp2c19', 'ambiguous', ...

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "description": self.description,
            "input": dict(self.input),
            "expected": dict(self.expected),
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class EvaluationResult:
    """Observed vs. expected outcome of one case."""

    case_id: str
    suite_name: str
    passed: bool
    observed: dict[str, Any] = field(default_factory=dict)
    expected: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    duration_ms: float = 0.0
    errors: tuple[str, ...] = ()
    recorded_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "suite_name": self.suite_name,
            "passed": self.passed,
            "observed": dict(self.observed),
            "expected": dict(self.expected),
            "metrics": dict(self.metrics),
            "reason": self.reason,
            "duration_ms": round(self.duration_ms, 2),
            "errors": list(self.errors),
            "recorded_at": self.recorded_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Suite summary
# ---------------------------------------------------------------------------


@dataclass
class SuiteSummary:
    """Aggregate stats after a suite run.

    Metric field semantics:
      pass_rate            fraction of cases where passed=True
      error_rate           fraction of cases with non-empty errors
      mean_duration_ms     per-case wall time
      aggregates           suite-specific rolling numbers (grounding
                           coverage, utilization, token totals, ...)
    """

    suite_name: str
    total_cases: int = 0
    passed: int = 0
    failed: int = 0
    errored: int = 0
    mean_duration_ms: float = 0.0
    aggregates: dict[str, Any] = field(default_factory=dict)
    results: list[EvaluationResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return round(self.passed / self.total_cases, 4)

    @property
    def error_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return round(self.errored / self.total_cases, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "total_cases": self.total_cases,
            "passed": self.passed,
            "failed": self.failed,
            "errored": self.errored,
            "pass_rate": self.pass_rate,
            "error_rate": self.error_rate,
            "mean_duration_ms": round(self.mean_duration_ms, 2),
            "aggregates": dict(self.aggregates),
            "results": [r.to_dict() for r in self.results],
        }


# ---------------------------------------------------------------------------
# Base suite
# ---------------------------------------------------------------------------


class EvaluationSuite(ABC):
    """Base class for every evaluation suite.

    Subclasses override ``run_case(case) -> EvaluationResult`` and
    optionally ``aggregate(results) -> dict`` to attach suite-
    specific rolling metrics.
    """

    name: str = "EvaluationSuite"

    # ------------------------------------------------------------------
    # Subclass contract
    # ------------------------------------------------------------------

    @abstractmethod
    def run_case(self, case: EvaluationCase) -> EvaluationResult:
        """Evaluate one case; return a populated EvaluationResult."""

    def aggregate(
        self, results: list[EvaluationResult]
    ) -> dict[str, Any]:
        """Override to attach suite-specific aggregate metrics."""
        return {}

    # ------------------------------------------------------------------
    # Driver
    # ------------------------------------------------------------------

    def run(self, cases: list[EvaluationCase]) -> SuiteSummary:
        """Iterate cases, call run_case, aggregate."""
        results: list[EvaluationResult] = []
        for case in cases:
            try:
                r = self.run_case(case)
            except Exception as exc:
                # Never let a single case's crash take down the suite.
                r = EvaluationResult(
                    case_id=case.case_id,
                    suite_name=self.name,
                    passed=False,
                    expected=dict(case.expected),
                    errors=(f"{type(exc).__name__}: {exc}",),
                    reason="suite.run_case raised",
                )
            results.append(r)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        errored = sum(1 for r in results if r.has_errors)
        mean_dur = (
            sum(r.duration_ms for r in results) / total if total else 0.0
        )
        return SuiteSummary(
            suite_name=self.name,
            total_cases=total,
            passed=passed,
            failed=total - passed,
            errored=errored,
            mean_duration_ms=mean_dur,
            aggregates=self.aggregate(results),
            results=results,
        )


__all__ = [
    "EvaluationCase",
    "EvaluationResult",
    "EvaluationSuite",
    "SuiteSummary",
]
