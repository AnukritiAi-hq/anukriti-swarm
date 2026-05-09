"""Composite evaluation suites — hallucination / population / reliability.

Closes reqs #2.4, #2.5, #2.6.

Three smaller suites bundled in one module — each leverages the
safety engine + observability primitives built in earlier sessions,
so the implementations are ~100 lines each.

    HallucinationPreventionSuite  req #2.4 — expects adversarial
                                   scenarios to BLOCK (block_rate
                                   + hallucination checks)
    PopulationAwareSuite           req #2.5 — expects per-population
                                   frequency attribution + prevalence
                                   signal on run outputs
    WorkflowReliabilitySuite       req #2.6 — end-to-end completion
                                   + failure rate + mean latency
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from agents.orchestrator.gemini_orchestrator import GeminiOrchestrator
from agents.verification import BiomedicalVerificationAgent
from integrations.mcp import MCPClient, MCPPersistenceHook

from evaluation.base import EvaluationCase, EvaluationResult, EvaluationSuite


# ---------------------------------------------------------------------------
# Hallucination prevention
# ---------------------------------------------------------------------------


@dataclass
class HallucinationPreventionSuite(EvaluationSuite):
    """Measures block rate on adversarial inputs (req #2.4).

    Runs each case directly through the verification agent (direct
    run_dict path) and asserts the safety engine either:
      1. blocks the output (SafetyDecision.block=True), OR
      2. emits at least one error-state trace (hard-fail signal)

    Either outcome means the engine caught the hallucination /
    drift / fabrication the case was designed to expose.

    Expects cases sourced from ``benchmarks.adversarial.ADVERSARIAL_SCENARIOS``
    or similarly shaped run_dicts. Running canonical (safe)
    scenarios through this suite is meaningless — pass_rate will
    be 0 because safe scenarios don't block.
    """

    name: str = "hallucination_prevention"
    client: MCPClient | None = None
    agent: BiomedicalVerificationAgent | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = MCPClient()
        if self.agent is None:
            self.agent = BiomedicalVerificationAgent(client=self.client)

    def run_case(self, case: EvaluationCase) -> EvaluationResult:
        t0 = time.perf_counter()
        run_dict = case.input.get("run_dict")
        if run_dict is None:
            return EvaluationResult(
                case_id=case.case_id,
                suite_name=self.name,
                passed=False,
                expected=dict(case.expected),
                reason="HallucinationPreventionSuite requires case.input['run_dict']",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )
        outcome = self.agent.verify_run(
            run_dict, correlation_id=f"hallu-{case.case_id}"
        )
        duration_ms = (time.perf_counter() - t0) * 1000

        blocked = bool(outcome.decision and outcome.decision.block)
        error_traces = sum(1 for t in outcome.traces if t.state == "fail")
        caught = blocked or error_traces > 0

        return EvaluationResult(
            case_id=case.case_id,
            suite_name=self.name,
            passed=caught,
            observed={
                "blocked": blocked,
                "error_traces": error_traces,
                "tier": outcome.tier,
            },
            expected=dict(case.expected),
            metrics={
                "blocked": blocked,
                "error_traces": error_traces,
                "tier": outcome.tier,
            },
            reason=(
                f"caught: block={blocked}, error_traces={error_traces}, tier={outcome.tier}"
                if caught
                else f"NOT caught: block={blocked}, error_traces=0, tier={outcome.tier}"
            ),
            duration_ms=duration_ms,
        )

    def aggregate(self, results: list[EvaluationResult]) -> dict[str, Any]:
        total = len(results)
        if total == 0:
            return {}
        blocked = sum(1 for r in results if r.metrics.get("blocked"))
        with_errors = sum(
            1 for r in results if int(r.metrics.get("error_traces") or 0) > 0
        )
        caught = sum(1 for r in results if r.passed)
        return {
            "catch_rate": round(caught / total, 4),
            "block_rate": round(blocked / total, 4),
            "error_trace_rate": round(with_errors / total, 4),
            "uncaught_count": total - caught,
        }


# ---------------------------------------------------------------------------
# Population-aware reasoning
# ---------------------------------------------------------------------------


@dataclass
class PopulationAwareSuite(EvaluationSuite):
    """Validates per-population frequency attribution + prevalence (req #2.5).

    For each case, asserts the population_result on the run carries:
      - a non-null ``population`` that matches case.input['population']
      - a ``frequency`` value if the scenario expects one
      - a ``confidence`` value propagated into verification

    Passes when population matches AND (no expected_frequency OR
    observed frequency is close to expected within 30% absolute).

    Aggregates: per-population pass rate + mean frequency error.
    """

    name: str = "population_aware_reasoning"
    freq_tolerance: float = 0.30  # 30% absolute
    orchestrator: GeminiOrchestrator | None = None
    client: MCPClient | None = None
    hook: MCPPersistenceHook | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = MCPClient()
        if self.orchestrator is None:
            self.orchestrator = GeminiOrchestrator()
        if self.hook is None:
            self.hook = MCPPersistenceHook(client=self.client)

    def run_case(self, case: EvaluationCase) -> EvaluationResult:
        t0 = time.perf_counter()
        inp = case.input
        try:
            result = self.orchestrator.run(
                gene=inp.get("gene", ""),
                drug=inp.get("drug", ""),
                population=inp.get("population", ""),
                allele1=inp.get("allele1"),
                allele2=inp.get("allele2"),
            )
        except Exception as exc:
            return EvaluationResult(
                case_id=case.case_id,
                suite_name=self.name,
                passed=False,
                expected=dict(case.expected),
                errors=(f"orchestrator.run: {type(exc).__name__}: {exc}",),
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        self.hook.persist(result)
        run0 = result.coordination.runs[0] if result.coordination.runs else {}
        pop_result = run0.get("population_result") or {}

        observed_pop = pop_result.get("population") or ""
        observed_freq = pop_result.get("frequency")
        observed_confidence = float(pop_result.get("confidence") or 0.0)

        expected_pop = inp.get("population", "")
        expected_freq = case.expected.get("frequency")

        pop_match = observed_pop == expected_pop
        freq_ok = True
        freq_error = 0.0
        if expected_freq is not None and observed_freq is not None:
            freq_error = abs(float(observed_freq) - float(expected_freq))
            freq_ok = freq_error <= self.freq_tolerance
        elif expected_freq is not None and observed_freq is None:
            freq_ok = False

        passed = pop_match and freq_ok
        duration_ms = (time.perf_counter() - t0) * 1000

        return EvaluationResult(
            case_id=case.case_id,
            suite_name=self.name,
            passed=passed,
            observed={
                "population": observed_pop,
                "frequency": observed_freq,
                "confidence": observed_confidence,
            },
            expected=dict(case.expected),
            metrics={
                "pop_match": pop_match,
                "freq_ok": freq_ok,
                "freq_error": round(freq_error, 4),
                "population": observed_pop,
                "confidence": observed_confidence,
            },
            reason=(
                f"pop={observed_pop} freq={observed_freq} (err={freq_error:.3f})"
                if passed
                else f"mismatch: pop_match={pop_match} freq_ok={freq_ok}"
            ),
            duration_ms=duration_ms,
        )

    def aggregate(self, results: list[EvaluationResult]) -> dict[str, Any]:
        total = len(results)
        if total == 0:
            return {}
        pop_match_count = sum(1 for r in results if r.metrics.get("pop_match"))
        freq_ok_count = sum(1 for r in results if r.metrics.get("freq_ok"))
        by_pop: dict[str, dict[str, int]] = {}
        for r in results:
            pop = str(r.metrics.get("population") or "")
            by_pop.setdefault(pop, {"total": 0, "passed": 0})
            by_pop[pop]["total"] += 1
            if r.passed:
                by_pop[pop]["passed"] += 1
        freq_errors = [
            float(r.metrics.get("freq_error") or 0.0)
            for r in results
            if r.observed.get("frequency") is not None
        ]
        return {
            "population_match_rate": round(pop_match_count / total, 4),
            "frequency_within_tolerance_rate": round(freq_ok_count / total, 4),
            "mean_frequency_error": (
                round(sum(freq_errors) / len(freq_errors), 4) if freq_errors else 0.0
            ),
            "by_population": by_pop,
            "freq_tolerance": self.freq_tolerance,
        }


# ---------------------------------------------------------------------------
# Workflow reliability
# ---------------------------------------------------------------------------


@dataclass
class WorkflowReliabilitySuite(EvaluationSuite):
    """End-to-end completion + failure rate + latency (req #2.6).

    A case passes when:
      1. orchestrator.run() completes without raising
      2. result.coordination.runs is non-empty
      3. a verification trace exists on the context

    Measures the most basic reliability signal: does the swarm
    complete its workflow end-to-end without crashing or dropping
    the context? Per-case metric: orchestration_latency_ms.

    Aggregates: completion_rate, mean/max/p95 orchestration latency.
    """

    name: str = "workflow_reliability"
    orchestrator: GeminiOrchestrator | None = None

    def __post_init__(self) -> None:
        if self.orchestrator is None:
            self.orchestrator = GeminiOrchestrator()

    def run_case(self, case: EvaluationCase) -> EvaluationResult:
        t0 = time.perf_counter()
        inp = case.input
        try:
            result = self.orchestrator.run(
                gene=inp.get("gene", ""),
                drug=inp.get("drug", ""),
                population=inp.get("population", ""),
                allele1=inp.get("allele1"),
                allele2=inp.get("allele2"),
            )
        except Exception as exc:
            return EvaluationResult(
                case_id=case.case_id,
                suite_name=self.name,
                passed=False,
                expected=dict(case.expected),
                errors=(f"orchestrator.run: {type(exc).__name__}: {exc}",),
                reason="orchestrator crashed",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        duration_ms = (time.perf_counter() - t0) * 1000

        has_runs = bool(result.coordination.runs)
        has_trace = result.context.orchestration_trace is not None
        completed = has_runs and has_trace

        return EvaluationResult(
            case_id=case.case_id,
            suite_name=self.name,
            passed=completed,
            observed={
                "has_runs": has_runs,
                "has_trace": has_trace,
                "run_count": len(result.coordination.runs),
                "total_duration_ms": round(result.total_duration_ms, 2),
            },
            expected=dict(case.expected),
            metrics={
                "completed": completed,
                "orchestration_latency_ms": result.total_duration_ms,
                "has_runs": has_runs,
                "has_trace": has_trace,
            },
            reason=(
                f"completed in {result.total_duration_ms:.1f}ms"
                if completed
                else f"incomplete: has_runs={has_runs}, has_trace={has_trace}"
            ),
            duration_ms=duration_ms,
        )

    def aggregate(self, results: list[EvaluationResult]) -> dict[str, Any]:
        total = len(results)
        if total == 0:
            return {}
        completed = sum(1 for r in results if r.metrics.get("completed"))
        latencies = [
            float(r.metrics.get("orchestration_latency_ms") or 0.0)
            for r in results
            if r.metrics.get("completed")
        ]
        mean_lat = sum(latencies) / len(latencies) if latencies else 0.0
        max_lat = max(latencies) if latencies else 0.0
        # Simple p95 — sorted index
        p95_lat = 0.0
        if latencies:
            idx = max(0, int(0.95 * len(latencies)) - 1)
            p95_lat = sorted(latencies)[idx]

        return {
            "completion_rate": round(completed / total, 4),
            "mean_latency_ms": round(mean_lat, 2),
            "max_latency_ms": round(max_lat, 2),
            "p95_latency_ms": round(p95_lat, 2),
            "failure_count": total - completed,
        }


__all__ = [
    "HallucinationPreventionSuite",
    "PopulationAwareSuite",
    "WorkflowReliabilitySuite",
]
