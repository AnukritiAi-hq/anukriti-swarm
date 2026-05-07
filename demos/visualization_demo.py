"""Anukriti Swarm — Execution Visualization Demo.

A compelling demonstration of distributed genomic intelligence:
CYP2C19 *2/*2 Poor Metabolizer on Clopidogrel in South Asian population.

Shows the swarm collaborating in real-time with full observability.

Run: python -m demos.visualization_demo
"""

from __future__ import annotations

import time

from visualization.export import export_trace_json
from visualization.graph.flow import render_confidence_propagation, render_evidence_flow, render_flow_graph
from visualization.traces.renderer import (
    render_confidence_bar,
    render_delegation,
    render_escalation,
    render_evidence,
    render_footer,
    render_header,
    render_stage_complete,
    render_verification_check,
)
from visualization.traces.timeline import ExecutionTimeline
from workflows.pipeline import run_pipeline


def run_demo() -> None:
    # Execute pipeline
    initial_state = {
        "gene": "CYP2C19",
        "drug": "clopidogrel",
        "population": "SAS",
        "allele1": "*2",
        "allele2": "*2",
    }

    state, trace = run_pipeline(initial_state)

    # --- Render visualization ---
    print(render_header(
        trace.correlation_id,
        state["gene"], state["drug"], state["population"],
    ))

    # Stage-by-stage trace with simulated real-time feel
    print("  ┌─ Swarm Execution Trace ──────────────────────────────────────┐")
    print("  │                                                                │")

    for s in trace.stages:
        detail = ""
        if s.stage == "orchestration":
            detail = f"dispatching {len(state.get('agents_dispatched', []))} agents"
        elif s.stage == "population":
            pop = state.get("population_result", {})
            detail = f"*2 freq={pop.get('frequency', '?')} in SAS"
        elif s.stage == "pharmacogene":
            pgx = state.get("pharmacogene_result", {})
            detail = f"{pgx.get('phenotype', '?')} → {pgx.get('risk', '?')}"
        elif s.stage == "retrieval":
            detail = f"{state.get('retrieval_count', 0)} passages, {state.get('grounding_score', 0):.0%} grounded"
        elif s.stage == "verification":
            v = state.get("verification", {})
            detail = f"{v.get('verdict', '?')} (conf={v.get('confidence', 0):.3f})"

        print(f"  │ {render_stage_complete(s.stage, s.stage, s.duration_ms, s.status, detail)}")

        # Show delegations for orchestration
        if s.stage == "orchestration":
            for agent in state.get("agents_dispatched", [])[:3]:
                print(f"  │ {render_delegation('orchestrator', agent, 'analyze')}")

        # Show evidence for retrieval
        if s.stage == "retrieval":
            for cit in state.get("citations", [])[:2]:
                print(f"  │ {render_evidence(cit, 0.93)}")

        # Show checks for verification
        if s.stage == "verification":
            for c in state.get("verification", {}).get("checks", [])[:3]:
                print(f"  │ {render_verification_check(c['name'], c['verdict'], c['reason'])}")

    print("  │                                                                │")
    print("  └────────────────────────────────────────────────────────────────┘")

    # Confidence propagation
    print()
    v = state.get("verification", {})
    stages_conf = {
        "phenotype": state.get("pharmacogene_result", {}).get("confidence", 1.0),
        "population": state.get("population_result", {}).get("confidence", 0.95),
        "grounding": state.get("grounding_score", 0.8),
    }
    print(render_confidence_propagation(stages_conf, v.get("confidence", 0)))

    # Flow graph
    print()
    print(render_flow_graph(state))

    # Evidence flow
    print()
    print(render_evidence_flow(state.get("citations", []), state.get("grounding_score", 0)))

    # Escalation decision
    print()
    print(render_escalation(v.get("escalation_tier", ""), v.get("action", "")))

    # Timeline
    print()
    timeline = ExecutionTimeline(trace.total_duration_ms)
    for s in trace.stages:
        timeline.add_stage(s.stage, s.stage, s.duration_ms, s.status)
    print(timeline.render())

    # Footer
    print(render_footer(trace.total_duration_ms, len(trace.stages), v.get("verdict", "pass")))

    # JSON export preview
    print(f"  {'\033[2m'}JSON export available: {len(export_trace_json(trace, state))} bytes{'\033[0m'}")
    print()


if __name__ == "__main__":
    run_demo()
