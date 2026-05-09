"""``SwarmEvaluationReport`` — aggregate report over all eval signals.

Closes req #5 of the evaluation brief. Single object holding every
artifact produced by a full evaluation run, plus publication-grade
renderers:

    .to_dict()       JSON-safe for dashboards + CI
    .to_markdown()   scorecard table for README / whitepaper

Composed inputs (all optional — supply what you ran):

    suite_summaries     dict[suite_name, SuiteSummary]
                         from the 6 evaluation suites
    stress_results      list[StressResult]
                         from benchmarks/stress.py
    ancestry_results    list[AncestryConflictResult]
                         from benchmarks/ancestry_conflicts.py
    metadata            dict — run_id, timestamp, git sha, etc.

Structure of the markdown report::

    1. Headline scorecard (overall pass rate + tier-level status)
    2. Per-suite table (name | total | passed | pass_rate)
    3. Per-suite aggregates (the suite's own metric dict)
    4. Stress test table
    5. Ancestry conflict table
    6. Reliability diagnostics (mean/p95 latency, failure rate)
    7. Safety outcomes (block rate + hallucination catch rate)

Every section is optional — missing data just skips that section
so partial runs still produce a valid report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from benchmarks.ancestry_conflicts import AncestryConflictResult
    from benchmarks.stress import StressResult
    from evaluation.base import SuiteSummary


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass
class SwarmEvaluationReport:
    """Aggregate report across every eval signal we collected."""

    run_id: str = ""
    suite_summaries: dict[str, "SuiteSummary"] = field(default_factory=dict)
    stress_results: list["StressResult"] = field(default_factory=list)
    ancestry_results: list["AncestryConflictResult"] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ------------------------------------------------------------------
    # Builders / mutators
    # ------------------------------------------------------------------

    def add_suite(self, summary: "SuiteSummary") -> None:
        self.suite_summaries[summary.suite_name] = summary

    def add_stress(self, results: list["StressResult"]) -> None:
        self.stress_results.extend(results)

    def add_ancestry(self, results: list["AncestryConflictResult"]) -> None:
        self.ancestry_results.extend(results)

    # ------------------------------------------------------------------
    # Top-line rollups
    # ------------------------------------------------------------------

    def headline(self) -> dict[str, Any]:
        """Top-level pass-rate / counts across every signal."""
        # Suite rollup.
        total_cases = sum(s.total_cases for s in self.suite_summaries.values())
        total_passed = sum(s.passed for s in self.suite_summaries.values())
        suite_pass_rate = (
            round(total_passed / total_cases, 4) if total_cases else 0.0
        )

        # Stress rollup.
        stress_total = len(self.stress_results)
        stress_passed = sum(1 for r in self.stress_results if r.passed)

        # Ancestry rollup.
        anc_total = len(self.ancestry_results)
        anc_passed = sum(1 for r in self.ancestry_results if r.passed)

        # Headline verdict: all green when every tier hits 100%; else
        # 'degraded' at <100% with no hard-fails; 'failed' at any suite
        # with pass_rate=0 or any catastrophic error.
        verdict = "all_pass"
        for s in self.suite_summaries.values():
            if s.pass_rate < 1.0:
                verdict = "degraded"
            if s.pass_rate == 0.0 and s.total_cases > 0:
                verdict = "failed"
                break

        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at.isoformat(),
            "overall_verdict": verdict,
            "suite_pass_rate": suite_pass_rate,
            "suite_cases_total": total_cases,
            "suite_cases_passed": total_passed,
            "stress_total": stress_total,
            "stress_passed": stress_passed,
            "ancestry_total": anc_total,
            "ancestry_passed": anc_passed,
        }

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at.isoformat(),
            "metadata": dict(self.metadata),
            "headline": self.headline(),
            "suites": {
                name: s.to_dict() for name, s in self.suite_summaries.items()
            },
            "stress": [r.to_dict() for r in self.stress_results],
            "ancestry": [r.to_dict() for r in self.ancestry_results],
        }

    # ------------------------------------------------------------------
    # Markdown
    # ------------------------------------------------------------------

    def to_markdown(self) -> str:
        lines: list[str] = []
        head = self.headline()

        # 1. Headline
        lines.append(f"# Anukriti Swarm — Evaluation Report")
        lines.append("")
        if self.run_id:
            lines.append(f"**Run id:** `{self.run_id}`  ")
        lines.append(f"**Generated:** {head['generated_at']}  ")
        lines.append(f"**Overall verdict:** `{head['overall_verdict']}`  ")
        lines.append(
            f"**Suite pass rate:** "
            f"{head['suite_cases_passed']}/{head['suite_cases_total']} "
            f"({head['suite_pass_rate']:.0%})  "
        )
        if head["stress_total"]:
            lines.append(
                f"**Stress:** {head['stress_passed']}/{head['stress_total']} passed  "
            )
        if head["ancestry_total"]:
            lines.append(
                f"**Ancestry divergence:** "
                f"{head['ancestry_passed']}/{head['ancestry_total']} passed  "
            )
        if self.metadata:
            for k, v in self.metadata.items():
                lines.append(f"**{k}:** {v}  ")
        lines.append("")

        # 2. Per-suite scorecard table
        if self.suite_summaries:
            lines.append("## Suite scorecard")
            lines.append("")
            lines.append(
                "| Suite | Total | Passed | Failed | Errored | Pass rate |"
            )
            lines.append(
                "|---|---|---|---|---|---|"
            )
            for name, s in sorted(self.suite_summaries.items()):
                lines.append(
                    f"| `{name}` | {s.total_cases} | {s.passed} | "
                    f"{s.failed} | {s.errored} | {s.pass_rate:.0%} |"
                )
            lines.append("")

        # 3. Per-suite aggregates
        if self.suite_summaries:
            lines.append("## Per-suite aggregates")
            lines.append("")
            for name, s in sorted(self.suite_summaries.items()):
                if not s.aggregates:
                    continue
                lines.append(f"### `{name}`")
                lines.append("")
                for k, v in s.aggregates.items():
                    if isinstance(v, dict):
                        lines.append(f"- **{k}:**")
                        for kk, vv in v.items():
                            lines.append(f"  - `{kk}`: {vv}")
                    else:
                        lines.append(f"- **{k}:** `{v}`")
                lines.append("")

        # 4. Stress table
        if self.stress_results:
            lines.append("## Stress test results")
            lines.append("")
            lines.append("| Scenario | Kind | Status | Reason |")
            lines.append("|---|---|---|---|")
            for r in self.stress_results:
                icon = "✅ PASS" if r.passed else "❌ FAIL"
                reason = (r.reason or "").replace("|", "/")[:80]
                lines.append(
                    f"| `{r.scenario_id}` | {r.kind} | {icon} | {reason} |"
                )
            lines.append("")

        # 5. Ancestry table
        if self.ancestry_results:
            lines.append("## Ancestry divergence results")
            lines.append("")
            lines.append(
                "| Scenario | Status | Divergence |"
            )
            lines.append("|---|---|---|")
            for r in self.ancestry_results:
                icon = "✅ PASS" if r.passed else "❌ FAIL"
                axes = []
                for axis, obs in (r.divergence_observed or {}).items():
                    axes.append(
                        f"{axis}: a={obs.get('a')} / b={obs.get('b')}"
                    )
                lines.append(
                    f"| `{r.scenario_id}` | {icon} | {'; '.join(axes)} |"
                )
            lines.append("")

        # 6. Reliability diagnostics — pulled from WorkflowReliabilitySuite
        reliability = self.suite_summaries.get("workflow_reliability")
        if reliability and reliability.aggregates:
            lines.append("## Reliability diagnostics")
            lines.append("")
            agg = reliability.aggregates
            lines.append(
                f"- **Completion rate:** `{agg.get('completion_rate', 0):.0%}`"
            )
            lines.append(
                f"- **Mean orchestration latency:** "
                f"`{agg.get('mean_latency_ms', 0)}ms`"
            )
            lines.append(
                f"- **p95 orchestration latency:** "
                f"`{agg.get('p95_latency_ms', 0)}ms`"
            )
            lines.append(
                f"- **Failure count:** `{agg.get('failure_count', 0)}`"
            )
            lines.append("")

        # 7. Safety outcomes — from verification + hallucination suites
        verif = self.suite_summaries.get("verification_accuracy")
        hallu = self.suite_summaries.get("hallucination_prevention")
        if verif or hallu:
            lines.append("## Safety outcomes")
            lines.append("")
            if verif and verif.aggregates:
                lines.append(
                    f"- **Verification block rate:** "
                    f"`{verif.aggregates.get('block_rate', 0):.0%}`"
                )
                lines.append(
                    f"- **Clean-tier delivery rate:** "
                    f"`{verif.aggregates.get('clean_tier_rate', 0):.0%}`"
                )
            if hallu and hallu.aggregates:
                lines.append(
                    f"- **Hallucination catch rate:** "
                    f"`{hallu.aggregates.get('catch_rate', 0):.0%}`"
                )
                lines.append(
                    f"- **Adversarial block rate:** "
                    f"`{hallu.aggregates.get('block_rate', 0):.0%}`"
                )
            lines.append("")

        return "\n".join(lines)


__all__ = ["SwarmEvaluationReport"]
