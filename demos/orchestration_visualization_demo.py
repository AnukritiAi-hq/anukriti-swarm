"""Anukriti Swarm — orchestration visualization demo.

Exercises every component of the ``observability`` package against
a live orchestration + safety run, and prints the four visual
outputs the brief names (orchestration graph, execution timeline,
evidence map, verification trace + provenance chain) plus the
profiler / activity / failure reports.

Run:
    python -m demos.orchestration_visualization_demo

What it shows:
  1. ExecutionTracer ingesting all 7 event kinds from a real run
  2. TimingProfiler bucketed p50/p95 latencies + token usage
  3. AgentActivityMonitor per-agent utilization + collaboration
  4. SwarmExecutionGraph nodes/edges with metadata
  5. TraceVisualizer VisualBundle (all 4 brief-named visuals)
  6. FailureAnalyzer hotspots against a deliberately broken run

No network required — the MCP client falls back to in-memory.
"""

from __future__ import annotations

from agents.orchestrator.gemini_orchestrator import GeminiOrchestrator
from agents.verification import BiomedicalVerificationAgent
from benchmarks.adversarial import ADVERSARIAL_SCENARIOS, run_scenario
from core.verification.escalation_workflow import EscalationWorkflow
from integrations.mcp import MCPClient, MCPPersistenceHook
from observability import (
    AgentActivityMonitor,
    ExecutionTracer,
    FailureAnalyzer,
    TimingProfiler,
    TraceVisualizer,
    WorkflowGraphBuilder,
)


# ANSI formatting (same palette as the other demos)
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


def run_demo() -> None:
    _banner(
        "👁  ANUKRITI SWARM — Orchestration Visualization",
        (
            "Execution tracing · Agent activity · Workflow graph · "
            "Safety checkpoints · Failure hotspots."
        ),
    )

    # ----- Wiring ------------------------------------------------------
    client = MCPClient()
    orch = GeminiOrchestrator()
    hook = MCPPersistenceHook(client=client)
    agent = BiomedicalVerificationAgent(client=client)

    tracer = ExecutionTracer()
    activity = AgentActivityMonitor()
    profiler = TimingProfiler()
    activity.attach(tracer)
    profiler.attach(tracer)

    print(f"  {D}  Backend mode: {client.mode}{R}")
    print(f"  {D}  Observability stack: tracer + profiler + activity monitor{R}")

    # -----------------------------------------------------------------
    # 1. Run a clean orchestration and ingest every source
    # -----------------------------------------------------------------
    _rule("1. Clean run — ingesting all event sources", GREEN)
    print(
        f"  {D}  Scenario: CYP2C19 *2/*2 + clopidogrel in SAS{R}\n"
    )
    result = orch.run(
        gene="CYP2C19", drug="clopidogrel", population="SAS",
        allele1="*2", allele2="*2",
    )
    hook.persist(result)
    outcome = agent.verify_run(
        result.coordination.runs[0],
        correlation_id=result.context.correlation_id,
    )
    tracer.ingest_orchestration_trace(result.context.orchestration_trace)
    tracer.ingest_mcp_snapshot(client.snapshot())
    tracer.ingest_verification_traces(outcome.traces)

    # Record a couple of synthetic token samples so the report isn't
    # empty. (The pipeline doesn't surface token usage yet; the
    # profiler accepts external samples so callers can plug in
    # whatever they measure.)
    profiler.record_tokens(agent="gemini.planner", input_tokens=1200, output_tokens=350)
    profiler.record_tokens(agent="gemini.narrator", input_tokens=800, output_tokens=600)

    print(f"  Tracer events:     {tracer.count()}")
    print(f"  Event kinds:       {tracer.summary()}")
    print(f"  Run total:         {result.total_duration_ms:.1f}ms")

    # -----------------------------------------------------------------
    # 2. Profiler report
    # -----------------------------------------------------------------
    _rule("2. TimingProfiler — latency buckets + token usage", YELLOW)
    report = profiler.latency_report()
    print(
        f"  Events seen: {report['total_events']}  "
        f"Failure rate: {report['failure_rate']:.0%}"
    )
    print(f"\n  {B}Latency by bucket:{R}")
    for bucket, stats in report["by_bucket"].items():
        print(
            f"    {bucket:<15} count={stats['count']:<3} "
            f"p50={stats['p50_ms']:>6.2f}ms  p95={stats['p95_ms']:>6.2f}ms  "
            f"total={stats['total_ms']}ms"
        )

    tokens = profiler.token_report()
    print(
        f"\n  {B}Token usage:{R} {tokens['total_tokens']} tokens / "
        f"{tokens['total_calls']} call(s)"
    )
    for agent_id, usage in tokens["by_agent"].items():
        print(
            f"    {agent_id:<25} in={usage['input_tokens']:>5} "
            f"out={usage['output_tokens']:>5} total={usage['total_tokens']}"
        )

    # -----------------------------------------------------------------
    # 3. Activity monitor
    # -----------------------------------------------------------------
    _rule("3. AgentActivityMonitor — utilization + collaboration", MAGENTA)
    act_report = activity.report(run_total_ms=result.total_duration_ms)
    print(f"  {B}Top agents:{R}")
    for a in act_report["agents"][:6]:
        print(
            f"    {a['agent_id']:<30} calls={a['call_count']:<3} "
            f"util={a['utilization']:.0%}  fail_rate={a['failure_rate']:.0%}"
        )
    print(f"\n  {B}Collaboration edges (top 5):{R}")
    for edge in act_report["collaborations"][:5]:
        print(
            f"    {edge['from']:<28} → {edge['to']:<28} x{edge['count']}"
        )

    # -----------------------------------------------------------------
    # 4. Graph + visual bundle
    # -----------------------------------------------------------------
    _rule("4. SwarmExecutionGraph + TraceVisualizer bundle", BLUE)
    builder = WorkflowGraphBuilder()
    graph = builder.build(
        tracer=tracer,
        activity=activity,
        profiler=profiler,
        outcome=outcome,
        correlation_id=result.context.correlation_id,
    )
    viz = TraceVisualizer()
    bundle = viz.render_all(
        run_dict=result.coordination.runs[0],
        outcome=outcome,
        graph=graph,
        tracer=tracer,
        total_duration_ms=result.total_duration_ms,
        correlation_id=result.context.correlation_id,
    )

    print(f"  Graph: {len(graph.nodes)} nodes  {len(graph.edges)} edges")
    print(f"  Nodes by kind: {graph.summary()['nodes_by_kind']}")
    print(f"  Edges by kind: {graph.summary()['edges_by_kind']}")
    print()
    print(f"  {B}Swarm map:{R}")
    print(bundle.swarm_map)
    print()
    print(f"  {B}Timeline:{R}")
    print(bundle.timeline)
    print()
    print(f"  {B}Evidence lineage:{R}")
    print(bundle.evidence_map)
    print()
    print(f"  {B}Verification checkpoints:{R}")
    print(bundle.verification_trace)

    # -----------------------------------------------------------------
    # 5. Mermaid export (for README embedding)
    # -----------------------------------------------------------------
    _rule("5. Mermaid graph export (first 12 lines)", CYAN)
    for line in bundle.mermaid_graph.splitlines()[:12]:
        print(f"  {line}")
    total_mermaid_lines = len(bundle.mermaid_graph.splitlines())
    print(f"  {D}  ...{total_mermaid_lines - 12} more line(s) omitted{R}")

    # -----------------------------------------------------------------
    # 6. Failure analysis — deliberately broken scenario
    # -----------------------------------------------------------------
    _rule("6. FailureAnalyzer — adversarial scenario hotspots", RED)
    print(
        f"  {D}  Running the ambiguous_genotype_phenotype_drift "
        f"scenario:{R}\n"
    )
    drift = ADVERSARIAL_SCENARIOS[1]
    scenario_result = run_scenario(drift, agent, EscalationWorkflow())
    analyzer = FailureAnalyzer()
    drift_summary = analyzer.analyze_outcome(scenario_result.outcome)

    print(f"  Tier:          {RED}{scenario_result.outcome.tier}{R}")
    print(f"  Errors:        {drift_summary.error_count}")
    print(f"  Warnings:      {drift_summary.warning_count}")
    print(f"  Failure rate:  {drift_summary.failure_rate:.0%}")
    print(f"\n  {B}Hotspots (validator, rule_id, count):{R}")
    for validator, rule_id, count in drift_summary.hotspots[:6]:
        print(f"    [{count}] {validator:<28} {rule_id}")

    # -----------------------------------------------------------------
    # Done
    # -----------------------------------------------------------------
    print(f"\n  {B}{'═' * 68}{R}")
    print(
        f"  {B}{CYAN}  {tracer.count()} events · "
        f"{len(graph.nodes)} nodes · "
        f"{len(graph.edges)} edges · "
        f"{tokens['total_tokens']} tokens · "
        f"{drift_summary.error_count} errors (adversarial){R}"
    )
    print(
        f"  {B}{CYAN}  Execution traced. Graph built. Visuals rendered. "
        f"Failures localized.{R}"
    )
    print(f"  {B}{'═' * 68}{R}\n")

    client.close()


if __name__ == "__main__":
    run_demo()
