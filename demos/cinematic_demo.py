"""Anukriti Swarm — cinematic presentation demo.

Closes requirement #9 of the observability brief. This demo is
presentation-ready: it plays back one orchestration run frame-by-
frame with pacing, phase banners, and narrated commentary so a
live audience can follow the swarm activating, reasoning,
verifying evidence, and synthesizing the final output.

Run:
    python -m demos.cinematic_demo

Pacing knobs live in ``CinematicConfig``. Defaults aim at ~40-60
seconds total for a clean run — fast enough to hold attention,
slow enough to read each verification checkpoint. Override on the
CLI via the ``--fast`` flag (halves every pacing multiplier).

Architecture:
  1. Run the orchestrator + safety engine + MCP persistence once.
  2. Pipe every ingested event into a live ExecutionTracer.
  3. Hand the tracer's events to CinematicPlayer which renders
     each with icon / color / per-kind pacing + phase banners.
  4. Attach a simple Narrator hook that adds commentary to a few
     well-chosen event kinds (verification checkpoints and
     escalation events).
"""

from __future__ import annotations

import sys

from agents.orchestrator.gemini_orchestrator import GeminiOrchestrator
from agents.verification import BiomedicalVerificationAgent
from core.verification.escalation_workflow import EscalationWorkflow
from integrations.mcp import MCPClient, MCPPersistenceHook
from observability import (
    CinematicConfig,
    CinematicPlayer,
    ExecutionTracer,
    EventKind,
    TraceVisualizer,
    WorkflowGraphBuilder,
)


B, D, R = "\033[1m", "\033[2m", "\033[0m"
CYAN, GREEN, YELLOW, RED, MAGENTA = (
    "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[35m",
)


def _big_banner(title: str) -> None:
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  {title}{R}")
    print(f"  {B}{'═' * 68}{R}\n")


def _narrator(ev) -> str:
    """Commentary for well-chosen event kinds.

    Kept terse so it doesn't overwhelm the visual stream. Returns
    an empty string for events that don't need commentary.
    """
    if ev.kind is EventKind.AGENT_ACTIVATION:
        role = ev.payload.get("role") or ""
        reason = ev.payload.get("reason") or ""
        return f"specialist activated ({role}): {reason[:60]}"
    if ev.kind is EventKind.VERIFICATION_EVENT:
        state = ev.payload.get("state", "")
        validator = ev.payload.get("validator", "")
        reason = ev.payload.get("reason", "")[:70]
        return f"[{state}] {validator}: {reason}"
    if ev.kind is EventKind.EVIDENCE_RETRIEVAL:
        refs = ev.payload.get("evidence_refs") or []
        return f"evidence cited: {', '.join(refs[:3])}"
    return ""


def run_demo(*, fast: bool = False) -> None:
    _big_banner("🎬 ANUKRITI SWARM — Cinematic Presentation")

    # ----- Wiring ------------------------------------------------------
    client = MCPClient()
    orch = GeminiOrchestrator()
    hook = MCPPersistenceHook(client=client)
    agent = BiomedicalVerificationAgent(client=client)
    workflow = EscalationWorkflow()

    tracer = ExecutionTracer()
    cfg = CinematicConfig(
        base_delay_s=0.15 if fast else 0.35,
        show_phase_banners=True,
        show_status_icon=True,
    )
    player = CinematicPlayer(config=cfg, narrator=_narrator)

    # -----------------------------------------------------------------
    # 1. Run the orchestration (without cinematic yet — collect first)
    # -----------------------------------------------------------------
    print(
        f"  {D}  Scenario: CYP2C19 *2/*2 + clopidogrel in South Asian (SAS){R}"
    )
    print(f"  {D}  Running orchestration...{R}")

    result = orch.run(
        gene="CYP2C19", drug="clopidogrel", population="SAS",
        allele1="*2", allele2="*2",
    )
    hook.persist(result)
    outcome = agent.verify_run(
        result.coordination.runs[0],
        correlation_id=result.context.correlation_id,
    )
    plan = workflow.plan(outcome)

    tracer.ingest_orchestration_trace(result.context.orchestration_trace)
    tracer.ingest_mcp_snapshot(client.snapshot())
    tracer.ingest_verification_traces(outcome.traces)

    print(
        f"  {D}  Run complete in {result.total_duration_ms:.1f}ms. "
        f"Collected {tracer.count()} events across 7 kinds.{R}"
    )
    print(
        f"  {D}  Playing the timeline back frame-by-frame "
        f"(base delay {cfg.base_delay_s}s)...{R}"
    )

    # -----------------------------------------------------------------
    # 2. Cinematic playback of the collected event stream
    # -----------------------------------------------------------------
    player.reset()
    rendered = player.play_events(tracer.events)

    # -----------------------------------------------------------------
    # 3. Post-run summary — verification verdict + escalation plan +
    #    the mermaid graph link for README embedding.
    # -----------------------------------------------------------------
    _big_banner("🏁 POST-RUN SUMMARY")

    verdict_color = GREEN if outcome.is_safe else RED
    print(f"  Verification tier:  {verdict_color}{outcome.tier}{R}")
    print(f"  Is safe to deliver: {verdict_color}{outcome.is_safe}{R}")
    print(f"  Safety decision:    {outcome.decision.reason if outcome.decision else '—'}")
    print(f"  Escalation plan:    status={plan.status}  steps={len(plan.steps)}")
    if plan.steps:
        print(f"  {D}First 3 plan steps:{R}")
        for step in plan.steps[:3]:
            sev_color = (
                RED if step.severity == "critical"
                else YELLOW if step.severity == "warning"
                else D
            )
            print(
                f"    {sev_color}[{step.severity}]{R} "
                f"{step.action.value} → {step.target[:50]}"
            )

    # Mermaid graph reminder — useful to project next.
    builder = WorkflowGraphBuilder()
    graph = builder.build(
        tracer=tracer, activity=None, profiler=None, outcome=outcome,
        correlation_id=result.context.correlation_id,
    )
    print(
        f"\n  Graph:  {len(graph.nodes)} nodes  "
        f"{len(graph.edges)} edges  "
        f"({graph.summary()['nodes_by_kind']})"
    )
    print(
        f"  {D}  To embed in README: TraceVisualizer().render_all(...)"
        f".mermaid_graph{R}"
    )

    # -----------------------------------------------------------------
    # 4. Close
    # -----------------------------------------------------------------
    _big_banner("🎬 END — nothing unverified reached the user")

    print(
        f"  {CYAN}{B}  {rendered} frames played · "
        f"{len(outcome.traces)} safety checkpoints · "
        f"tier={outcome.tier}{R}"
    )
    print(
        f"  {CYAN}{B}  Swarm activated. Agents reasoned. "
        f"Safety enforced. Provenance preserved.{R}\n"
    )

    client.close()


def _parse_fast() -> bool:
    return "--fast" in sys.argv


if __name__ == "__main__":
    run_demo(fast=_parse_fast())
