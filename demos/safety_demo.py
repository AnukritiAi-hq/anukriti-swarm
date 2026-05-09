"""Anukriti Swarm — Deterministic Safety Engine demo.

Closes requirement #11 of the safety brief.

Demonstrates the full safety pipeline end-to-end:

    1. A clean orchestration run — verified, grounded, delivered
       with the full audit report
    2. Four adversarial scenarios — each exercises a specific
       failure mode and shows the engine *blocking* or
       *escalating* correctly:
         conflicting evidence  → tier=CONFLICTING, BLOCK
         ambiguous genotype    → tier=UNSAFE,      BLOCK
         missing evidence      → tier=UNVERIFIED,  REQUEST_EVIDENCE
         ancestry edge case    → tier=UNVERIFIED,  REROUTE
    3. Governance audit — one end-of-demo summary table so hackathon
       judges see the full engine behaviour at a glance

Run:
    python -m demos.safety_demo
"""

from __future__ import annotations

from agents.orchestrator.gemini_orchestrator import GeminiOrchestrator
from agents.verification import BiomedicalVerificationAgent
from benchmarks.adversarial import ADVERSARIAL_SCENARIOS, run_scenario
from core.verification.escalation_workflow import EscalationWorkflow
from integrations.mcp import MCPClient, MCPPersistenceHook


# ---------------------------------------------------------------------------
# ANSI formatting (same aesthetic as demos/mcp_infrastructure_demo)
# ---------------------------------------------------------------------------

B, D, R = "\033[1m", "\033[2m", "\033[0m"
CYAN, GREEN, YELLOW, RED, MAGENTA, BLUE = (
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
    "\033[35m",
    "\033[34m",
)


def _rule(title: str = "", color: str = CYAN) -> None:
    if title:
        print(f"\n  {B}{color}  {title}{R}")
    print(f"  {B}{'─' * 68}{R}")


def _banner(title: str, subtitle: str = "") -> None:
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  {title}{R}")
    print(f"  {B}{'═' * 68}{R}")
    if subtitle:
        print(f"  {D}  {subtitle}{R}\n")


def _verdict_color(tier: str) -> str:
    return (
        GREEN if tier == "grounded"
        else YELLOW if tier == "partially_grounded"
        else MAGENTA if tier == "unverified"
        else RED
    )


def _status_icon(passed: bool, blocked: bool) -> str:
    if blocked:
        return f"{RED}■ BLOCKED{R}"
    if passed:
        return f"{GREEN}✓ DELIVERED{R}"
    return f"{YELLOW}⚠ CAVEATED{R}"


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------


def run_demo() -> None:
    _banner(
        "🛡️  ANUKRITI SWARM — Deterministic Safety Engine",
        (
            "Nothing unverified ever reaches the user. "
            "Evidence-backed. Block-on-unsafe. Auditable."
        ),
    )

    # ----- Wiring ------------------------------------------------------
    client = MCPClient()
    orch = GeminiOrchestrator()
    hook = MCPPersistenceHook(client=client)
    agent = BiomedicalVerificationAgent(client=client)
    workflow = EscalationWorkflow()

    print(f"  {D}  Backend mode: {client.mode}{R}")
    print(f"  {D}  Agent: BiomedicalVerificationAgent ({4} engines wired){R}")
    print(f"  {D}  Workflow: EscalationWorkflow (4 action kinds){R}")

    # -----------------------------------------------------------------
    # 1. Clean run — full pipeline, full audit
    # -----------------------------------------------------------------
    _rule("1. Clean run — evidence-backed reasoning", GREEN)
    print(
        f"  {D}  Scenario: CYP2C19 *2/*2 + clopidogrel in SAS — the "
        f"canonical safe path{R}\n"
    )
    result = orch.run(
        gene="CYP2C19", drug="clopidogrel", population="SAS",
        allele1="*2", allele2="*2",
    )
    hook.persist(result)   # populate MCP so grounding/provenance work
    outcome = agent.verify_run(
        result.coordination.runs[0],
        correlation_id=result.context.correlation_id,
    )
    plan = workflow.plan(outcome)

    print(
        f"  Tier:     {_verdict_color(outcome.tier)}{outcome.tier}{R}  "
        f"Safe: {GREEN if outcome.is_safe else RED}"
        f"{outcome.is_safe}{R}  "
        f"Plan: {plan.status}"
    )
    print(f"  Traces:   {len(outcome.traces)} per-claim records")
    if outcome.grounding:
        g = outcome.grounding
        print(
            f"  Evidence: {g.sources_resolved}/{g.sources_requested} "
            f"source(s) resolved (coverage={g.coverage:.0%})"
        )
    if outcome.provenance:
        p = outcome.provenance
        print(
            f"  Provenance: {p.records_examined} record(s), "
            f"{'clean' if p.is_clean else 'with gaps'}"
        )
    print()
    print(f"  {D}  Full audit report:{R}\n")
    for line in agent.audit_report(outcome).splitlines():
        print(f"  {line}")

    # -----------------------------------------------------------------
    # 2. Adversarial scenarios — the failure paths
    # -----------------------------------------------------------------
    _rule("2. Adversarial scenarios — unsafe outputs blocked", RED)
    print(
        f"  {D}  4 scenarios, each exercising one specific failure "
        f"path.{R}\n"
    )

    results = []
    for scn in ADVERSARIAL_SCENARIOS:
        res = run_scenario(scn, agent, workflow)
        results.append(res)

        tier_color = _verdict_color(res.outcome.tier)
        status = _status_icon(res.outcome.is_safe, res.plan.is_blocked)

        print(f"  {B}{scn.kind.upper()}{R} — {scn.scenario_id}")
        print(f"    {D}{scn.description}{R}")
        print(
            f"    Engine says: tier={tier_color}{res.outcome.tier:<20}{R}"
            f" is_safe={res.outcome.is_safe}"
        )
        print(
            f"    Workflow:    plan={res.plan.status:<10} "
            f"steps={len(res.plan.steps):<3}  → {status}"
        )

        # Show the first 3 steps for context
        for step in res.plan.steps[:3]:
            sev_color = (
                RED if step.severity == "critical"
                else YELLOW if step.severity == "warning"
                else D
            )
            print(
                f"      {sev_color}• [{step.severity}] "
                f"{step.action.value}{R} → {step.target[:45]}"
            )
        if len(res.plan.steps) > 3:
            print(f"      {D}  (+{len(res.plan.steps) - 3} more){R}")

        expectation = "✓ expected" if res.passed else "✗ mismatch"
        color = GREEN if res.passed else RED
        print(f"    {color}{expectation}{R}")
        print()

    # -----------------------------------------------------------------
    # 3. Governance audit summary
    # -----------------------------------------------------------------
    _rule("3. Governance audit — end-of-demo summary", BLUE)

    total = len(results) + 1  # +1 for the clean run
    delivered = sum(1 for r in results if not r.plan.is_blocked)
    blocked = sum(1 for r in results if r.plan.is_blocked)
    all_scenarios_passed = all(r.passed for r in results)

    print(f"  {B}{'Scenario':<40} {'Tier':<20} {'Plan':<12} {'Status':<12}{R}")
    print(f"  {B}{'─' * 68}{R}")
    print(
        f"  {'clean_run (canonical safe path)':<40} "
        f"{_verdict_color(outcome.tier)}{outcome.tier:<20}{R} "
        f"{plan.status:<12} {_status_icon(outcome.is_safe, plan.is_blocked)}"
    )
    for r in results:
        print(
            f"  {r.scenario_id:<40} "
            f"{_verdict_color(r.outcome.tier)}{r.outcome.tier:<20}{R} "
            f"{r.plan.status:<12} "
            f"{_status_icon(r.outcome.is_safe, r.plan.is_blocked)}"
        )

    print()
    print(
        f"  {D}Total scenarios: {total}  "
        f"delivered: {delivered + 1}  "  # +1 for clean
        f"blocked: {blocked}{R}"
    )
    print(
        f"  {D}Adversarial tests: "
        f"{sum(1 for r in results if r.passed)}/{len(results)} "
        f"matched expectations{R}"
    )
    print()
    assertion_color = GREEN if all_scenarios_passed else RED
    print(
        f"  {assertion_color}{B}"
        f"  Safety engine {'enforced' if all_scenarios_passed else 'FAILED'} "
        f"every expected constraint.{R}"
    )

    # -----------------------------------------------------------------
    # Done
    # -----------------------------------------------------------------
    print(f"\n  {B}{'═' * 68}{R}")
    print(
        f"  {B}{CYAN}  Deterministic verification. "
        f"Evidence-backed. Block-on-unsafe.{R}"
    )
    print(
        f"  {B}{CYAN}  Nothing unverified reaches the user.{R}"
    )
    print(f"  {B}{'═' * 68}{R}\n")

    client.close()


if __name__ == "__main__":
    run_demo()
