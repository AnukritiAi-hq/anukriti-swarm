"""``VerificationAccuracySuite`` — closes req #2.2.

Runs the full safety engine (BiomedicalVerificationAgent) against
each scenario and asserts the observed tier + block decision
matches what the scenario declares.

Why a separate suite from OrchestrationAccuracy?
------------------------------------------------
Orchestration accuracy answers "does the pipeline produce the
right phenotype / risk / verdict?". Verification accuracy answers
"does the safety engine correctly accept or reject that output?".
Both matter — a pipeline can produce the right phenotype but
the safety engine can still over- or under-block.

For the 12 canonical scenarios, expected behaviour is "safe to
deliver" (tier in {grounded, partially_grounded}, block=False).
The suite asserts that. For any scenario explicitly marked
adversarial (via tags), the expected behaviour flips — those
cases are validated via ``VerificationAccuracySuite.for_adversarial()``.

Metrics attached per case
-------------------------
    observed_tier          safety tier emitted
    observed_block         block flag from SafetyDecision
    expected_tier          (when supplied)
    expected_block         (when supplied)
    trace_count            number of VerificationTraces produced

Aggregates
----------
    tier_distribution      count per tier across all cases
    block_rate             fraction of cases where block=True
    clean_tier_rate        fraction of cases in {grounded,
                            partially_grounded}
    mean_trace_count       average traces per run
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from agents.orchestrator.gemini_orchestrator import GeminiOrchestrator
from agents.verification import BiomedicalVerificationAgent
from integrations.mcp import MCPClient, MCPPersistenceHook

from evaluation.base import EvaluationCase, EvaluationResult, EvaluationSuite


# Canonical scenarios are expected to deliver (safe).
_SAFE_TIERS = {"grounded", "partially_grounded"}


@dataclass
class VerificationAccuracySuite(EvaluationSuite):
    """Runs BiomedicalVerificationAgent against each case.

    Constructor injects orchestrator + agent + hook so tests can
    supply stubs. Default wiring uses in-memory MCP so the suite
    works offline.

    ``mode`` switches between two evaluation policies:

      "canonical"   expect is_safe=True, tier in safe_tiers
                    (default, used for the 12 canonical scenarios)
      "adversarial" expect is_safe=False, block=True
                    (used for adversarial scenarios in commit 8)
    """

    name: str = "verification_accuracy"
    mode: str = "canonical"
    client: MCPClient | None = None
    orchestrator: GeminiOrchestrator | None = None
    agent: BiomedicalVerificationAgent | None = None
    hook: MCPPersistenceHook | None = None
    # Scenarios already marked with specific expectations in
    # ``case.expected['tier']`` override the mode default.
    safe_tiers: tuple[str, ...] = ("grounded", "partially_grounded")

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = MCPClient()
        if self.orchestrator is None:
            self.orchestrator = GeminiOrchestrator()
        if self.hook is None:
            self.hook = MCPPersistenceHook(client=self.client)
        if self.agent is None:
            self.agent = BiomedicalVerificationAgent(client=self.client)

    # ------------------------------------------------------------------
    # Factory for adversarial evaluation
    # ------------------------------------------------------------------

    @classmethod
    def for_adversarial(cls, **kwargs: Any) -> "VerificationAccuracySuite":
        """Suite configured for adversarial cases (expects block=True)."""
        return cls(mode="adversarial", **kwargs)

    # ------------------------------------------------------------------
    # Suite contract
    # ------------------------------------------------------------------

    def run_case(self, case: EvaluationCase) -> EvaluationResult:
        # Two evaluation paths:
        #   direct_run=True in the input dict -> skip the orchestrator,
        #     feed the scenario's synthetic run_dict directly to the
        #     verification agent. Used for adversarial scenarios whose
        #     crafted run_dict is the whole point of the evaluation
        #     (orchestrator would produce a healthy run and miss the
        #     intended failure mode).
        #   default -> run the orchestrator then verify its output.
        t0 = time.perf_counter()
        direct_run = case.input.get("run_dict")

        if direct_run is not None:
            try:
                outcome = self.agent.verify_run(
                    direct_run,
                    correlation_id=f"eval-{case.case_id}",
                )
            except Exception as exc:
                return EvaluationResult(
                    case_id=case.case_id,
                    suite_name=self.name,
                    passed=False,
                    expected=dict(case.expected),
                    errors=(f"agent.verify_run: {type(exc).__name__}: {exc}",),
                    reason="direct verification crashed",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )
            duration_ms = (time.perf_counter() - t0) * 1000
        else:
            # Run the full orchestrator first.
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
                    errors=(
                        f"orchestrator.run: {type(exc).__name__}: {exc}",
                    ),
                    reason="orchestration crashed",
                    duration_ms=(time.perf_counter() - t0) * 1000,
                )

            self.hook.persist(result)
            run0 = (
                result.coordination.runs[0]
                if result.coordination.runs
                else {}
            )
            outcome = self.agent.verify_run(
                run0, correlation_id=result.context.correlation_id
            )
            duration_ms = (time.perf_counter() - t0) * 1000

        observed_tier = outcome.tier
        observed_block = bool(
            outcome.decision and outcome.decision.block
        )
        trace_count = len(outcome.traces)

        expected_tier = case.expected.get("tier")
        expected_block = case.expected.get("block")

        # Decide pass/fail based on mode (or explicit expectations).
        passed, reason = self._judge(
            observed_tier=observed_tier,
            observed_block=observed_block,
            expected_tier=expected_tier,
            expected_block=expected_block,
        )

        return EvaluationResult(
            case_id=case.case_id,
            suite_name=self.name,
            passed=passed,
            observed={
                "tier": observed_tier,
                "block": observed_block,
                "is_safe": outcome.is_safe,
                "trace_count": trace_count,
            },
            expected=dict(case.expected),
            metrics={
                "observed_tier": observed_tier,
                "observed_block": observed_block,
                "trace_count": trace_count,
                "confidence": (
                    outcome.decision.score.confidence
                    if outcome.decision else 0.0
                ),
            },
            reason=reason,
            duration_ms=duration_ms,
        )

    def aggregate(self, results: list[EvaluationResult]) -> dict[str, Any]:
        total = len(results)
        if total == 0:
            return {}
        tier_dist: dict[str, int] = {}
        blocks = 0
        safe = 0
        sum_traces = 0
        for r in results:
            tier = str(r.metrics.get("observed_tier") or "")
            tier_dist[tier] = tier_dist.get(tier, 0) + 1
            if r.metrics.get("observed_block"):
                blocks += 1
            if tier in self.safe_tiers:
                safe += 1
            sum_traces += int(r.metrics.get("trace_count") or 0)
        return {
            "tier_distribution": tier_dist,
            "block_rate": round(blocks / total, 4),
            "clean_tier_rate": round(safe / total, 4),
            "mean_trace_count": round(sum_traces / total, 2),
            "mode": self.mode,
        }

    # ------------------------------------------------------------------
    # Judgement
    # ------------------------------------------------------------------

    def _judge(
        self,
        *,
        observed_tier: str,
        observed_block: bool,
        expected_tier: str | None,
        expected_block: bool | None,
    ) -> tuple[bool, str]:
        """Decide pass/fail; explicit expectations win, else mode default."""

        # If the case declares explicit expectations, honour them.
        if expected_tier is not None or expected_block is not None:
            ok = True
            parts: list[str] = []
            if expected_tier is not None and observed_tier != expected_tier:
                ok = False
                parts.append(
                    f"tier: expected={expected_tier} observed={observed_tier}"
                )
            if expected_block is not None and observed_block != expected_block:
                ok = False
                parts.append(
                    f"block: expected={expected_block} observed={observed_block}"
                )
            if ok:
                return (
                    True,
                    f"tier={observed_tier}, block={observed_block} — as expected",
                )
            return False, "; ".join(parts)

        # Fall back to mode defaults.
        if self.mode == "canonical":
            ok = observed_tier in self.safe_tiers and not observed_block
            if ok:
                return (
                    True,
                    f"tier={observed_tier} in safe set, not blocked — canonical case passes",
                )
            return False, (
                f"canonical mode: tier={observed_tier} block={observed_block} — "
                f"expected tier in {sorted(self.safe_tiers)} and block=False"
            )
        if self.mode == "adversarial":
            ok = observed_block is True
            if ok:
                return (
                    True,
                    f"tier={observed_tier}, block=True — adversarial case correctly refused",
                )
            return False, (
                f"adversarial mode: tier={observed_tier} block={observed_block} — "
                "expected block=True"
            )
        return False, f"unknown mode {self.mode!r}"


__all__ = ["VerificationAccuracySuite"]
