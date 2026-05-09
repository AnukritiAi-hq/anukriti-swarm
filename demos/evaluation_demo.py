"""Anukriti Swarm — full evaluation sweep demo.

Runs every component of the evaluation framework in one shot and
prints the consolidated ``SwarmEvaluationReport``. This is the
demo that produces the numbers the whitepaper + architecture doc
cite.

Sections:
  1. Run all 6 evaluation suites against canonical + adversarial
     scenarios
  2. Run the 4 stress scenarios
  3. Run the 3 ancestry-conflict scenarios
  4. Aggregate everything into a SwarmEvaluationReport
  5. Print the headline scorecard + verdict + markdown preview

Run:
    python -m demos.evaluation_demo

Produces a markdown report at /tmp/swarm-evaluation-<run-id>.md
that can be embedded directly into README / whitepaper / grant
application. No network required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from benchmarks.adversarial import ADVERSARIAL_SCENARIOS
from benchmarks.ancestry_conflicts import run_all_ancestry_conflicts
from benchmarks.scenarios import (
    CYP2C19_SCENARIOS,
    CYP2D6_SCENARIOS,
    HLA_B_SCENARIOS,
)
from benchmarks.stress import run_stress_scenarios
from evaluation import (
    EvaluationCase,
    EvidenceGroundingSuite,
    HallucinationPreventionSuite,
    OrchestrationAccuracySuite,
    PopulationAwareSuite,
    SwarmEvaluationReport,
    VerificationAccuracySuite,
    WorkflowReliabilitySuite,
    cases_from_scenarios,
)


# ANSI palette
B, D, R = "\033[1m", "\033[2m", "\033[0m"
CYAN, GREEN, YELLOW, RED, MAGENTA, BLUE = (
    "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[35m", "\033[34m",
)


def _banner(title: str, subtitle: str = "") -> None:
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  {title}{R}")
    print(f"  {B}{'═' * 68}{R}")
    if subtitle:
        print(f"  {D}  {subtitle}{R}\n")


def _rule(title: str, color: str = CYAN) -> None:
    print(f"\n  {B}{color}  {title}{R}")
    print(f"  {B}{'─' * 68}{R}")


def _verdict_color(verdict: str) -> str:
    return {"all_pass": GREEN, "degraded": YELLOW, "failed": RED}.get(
        verdict, D
    )


def run_demo() -> None:
    _banner(
        "📊 ANUKRITI SWARM — Full Evaluation Sweep",
        (
            "6 suites · 4 stress tests · 3 ancestry conflicts · "
            "consolidated report"
        ),
    )

    run_id = f"eval-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    report = SwarmEvaluationReport(run_id=run_id)
    report.metadata = {
        "scope": "full sweep",
        "canonical_scenarios": len(
            CYP2C19_SCENARIOS + CYP2D6_SCENARIOS + HLA_B_SCENARIOS
        ),
        "adversarial_scenarios": len(ADVERSARIAL_SCENARIOS),
    }

    # -----------------------------------------------------------------
    # 1. Eval suites
    # -----------------------------------------------------------------
    _rule("1. Running 6 evaluation suites", CYAN)

    # Use all 12 canonical scenarios across suites that accept them;
    # hallucination-prevention gets adversarial cases.
    canonical = cases_from_scenarios(
        CYP2C19_SCENARIOS + CYP2D6_SCENARIOS + HLA_B_SCENARIOS
    )
    adversarial_cases = [
        EvaluationCase(
            case_id=a.scenario_id,
            description=a.description,
            input={"run_dict": a.run_dict},
            expected={"block": a.expected_block, "kind": a.kind},
            tags=("adversarial", a.kind),
        )
        for a in ADVERSARIAL_SCENARIOS
    ]

    suites = [
        ("orchestration_accuracy",
         OrchestrationAccuracySuite(), canonical),
        ("verification_accuracy",
         VerificationAccuracySuite(), canonical),
        ("evidence_grounding",
         EvidenceGroundingSuite(), canonical),
        ("hallucination_prevention",
         HallucinationPreventionSuite(), adversarial_cases),
        ("population_aware_reasoning",
         PopulationAwareSuite(),
         # HLA-B has no frequency data in the fixture store, so
         # filter to CYP scenarios for this suite.
         cases_from_scenarios(CYP2C19_SCENARIOS + CYP2D6_SCENARIOS)),
        ("workflow_reliability",
         WorkflowReliabilitySuite(), canonical),
    ]

    for name, suite, cases in suites:
        print(f"  {D}  running {name} on {len(cases)} case(s)...{R}", end=" ")
        summary = suite.run(cases)
        report.add_suite(summary)
        color = GREEN if summary.pass_rate == 1.0 else YELLOW if summary.pass_rate > 0.5 else RED
        print(
            f"{color}{summary.passed}/{summary.total_cases} "
            f"({summary.pass_rate:.0%}){R}"
        )

    # -----------------------------------------------------------------
    # 2. Stress
    # -----------------------------------------------------------------
    _rule("2. Running 4 stress-test scenarios", YELLOW)
    stress_results = run_stress_scenarios()
    report.add_stress(stress_results)
    for r in stress_results:
        icon = f"{GREEN}✓{R}" if r.passed else f"{RED}✗{R}"
        print(f"  {icon} {r.scenario_id:<40} {r.reason[:60]}")

    # -----------------------------------------------------------------
    # 3. Ancestry conflicts
    # -----------------------------------------------------------------
    _rule("3. Running 3 ancestry-conflict scenarios", MAGENTA)
    ancestry_results = run_all_ancestry_conflicts()
    report.add_ancestry(ancestry_results)
    for r in ancestry_results:
        icon = f"{GREEN}✓{R}" if r.passed else f"{RED}✗{R}"
        print(f"  {icon} {r.scenario_id:<40} {r.reason}")

    # -----------------------------------------------------------------
    # 4. Headline
    # -----------------------------------------------------------------
    _banner("🏁 CONSOLIDATED REPORT")

    head = report.headline()
    verdict_color = _verdict_color(head["overall_verdict"])
    print(f"  {B}Run id:            {run_id}{R}")
    print(f"  {B}Overall verdict:   {verdict_color}{head['overall_verdict']}{R}")
    print(
        f"  {B}Suite pass rate:   {GREEN}"
        f"{head['suite_cases_passed']}/{head['suite_cases_total']} "
        f"({head['suite_pass_rate']:.0%}){R}"
    )
    print(
        f"  {B}Stress tests:      {GREEN}"
        f"{head['stress_passed']}/{head['stress_total']}{R}"
    )
    print(
        f"  {B}Ancestry divergence:{GREEN}"
        f"{head['ancestry_passed']}/{head['ancestry_total']}{R}"
    )

    # -----------------------------------------------------------------
    # 5. Write markdown report to disk
    # -----------------------------------------------------------------
    _rule("5. Markdown report", BLUE)
    md = report.to_markdown()
    out_path = Path(f"/tmp/swarm-evaluation-{run_id}.md")
    out_path.write_text(md)
    print(f"  {D}  Wrote {len(md.splitlines())} lines to {out_path}{R}")
    print()
    print(f"  {D}  First 30 lines:{R}")
    print()
    for line in md.splitlines()[:30]:
        print(f"  {line}")
    print(f"  {D}  ...{R}")

    # -----------------------------------------------------------------
    # Close
    # -----------------------------------------------------------------
    print(f"\n  {B}{'═' * 68}{R}")
    print(
        f"  {B}{CYAN}  "
        f"{head['suite_cases_passed']}/{head['suite_cases_total']} suite cases · "
        f"{head['stress_passed']}/{head['stress_total']} stress · "
        f"{head['ancestry_passed']}/{head['ancestry_total']} ancestry{R}"
    )
    print(
        f"  {B}{CYAN}  Measurable reliability. Grounded evidence. "
        f"Population-aware safety.{R}"
    )
    print(f"  {B}{'═' * 68}{R}\n")


if __name__ == "__main__":
    run_demo()
