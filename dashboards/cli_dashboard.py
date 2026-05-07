"""CLI dashboard rendering for swarm observability.

Renders rich terminal dashboards showing:
- Agent activity summary
- Execution metrics
- Confidence propagation
- Evidence quality
- Provenance timeline
"""

from __future__ import annotations

from typing import Any

from metrics.collector import PipelineMetrics


def render_dashboard(metrics: PipelineMetrics, state: dict[str, Any]) -> str:
    """Render a full observability dashboard."""
    pgx = state.get("pharmacogene_result", {})
    pop = state.get("population_result", {})
    v = state.get("verification", {})

    lines = [
        "",
        "  ╔══════════════════════════════════════════════════════════════════╗",
        "  ║  🧬 ANUKRITI SWARM — Observability Dashboard                   ║",
        "  ╠══════════════════════════════════════════════════════════════════╣",
        f"  ║  Correlation: {metrics.correlation_id:<48} ║",
        "  ╠══════════════════════════════════════════════════════════════════╣",
        "",
        "  ┌─ Execution Metrics ─────────────────────────────────────────────┐",
        f"  │  Total Duration:    {metrics.total_duration_ms:>6.1f} ms                                │",
        f"  │  Stages:            {metrics.stage_count:>6}                                    │",
        f"  │  Agents:            {len(metrics.agents_participated):>6}                                    │",
        f"  │  Deterministic:     {metrics.deterministic_stages:>6}                                    │",
        f"  │  Generative:        {metrics.generative_stages:>6}                                    │",
        "  └─────────────────────────────────────────────────────────────────┘",
        "",
        "  ┌─ Agent Activity ────────────────────────────────────────────────┐",
    ]

    for s in metrics.stages:
        bar = "█" * max(1, int(s.duration_ms / max(metrics.total_duration_ms, 0.1) * 30))
        icon = "✓" if s.status == "success" else "⚠" if s.status == "warning" else "✗"
        lines.append(f"  │  {icon} {s.agent_id:<18} {bar:<30} {s.duration_ms:>5.1f}ms │")

    lines.extend([
        "  └─────────────────────────────────────────────────────────────────┘",
        "",
        "  ┌─ Quality Metrics ───────────────────────────────────────────────┐",
        f"  │  Grounding Score:   {'█' * int(metrics.grounding_score * 20)}{'░' * (20 - int(metrics.grounding_score * 20))} {metrics.grounding_score:.0%}          │",
        f"  │  Confidence:        {'█' * int(metrics.confidence_final * 20)}{'░' * (20 - int(metrics.confidence_final * 20))} {metrics.confidence_final:.3f}       │",
        f"  │  Citations:         {metrics.citation_count:>3}                                       │",
        f"  │  Verification:      {metrics.verification_verdict.upper():<10}                              │",
        f"  │  Escalation:        {metrics.escalation_tier:<20}                    │",
        "  └─────────────────────────────────────────────────────────────────┘",
        "",
        "  ┌─ Reasoning Introspection ──────────────────────────────────────┐",
        f"  │  Gene:       {pgx.get('gene', '?'):<15} Drug:     {state.get('drug', '?'):<15}     │",
        f"  │  Diplotype:  {pgx.get('diplotype', '?'):<15} Phenotype: {pgx.get('phenotype', '?'):<14}│",
        f"  │  Population: {pop.get('population', '?'):<15} Frequency: {str(pop.get('frequency', '?')):<14}│",
        f"  │  Risk:       {pgx.get('risk', '?'):<15} Origin:    {pgx.get('origin', '?'):<14}│",
        "  └─────────────────────────────────────────────────────────────────┘",
        "",
        "  ╚══════════════════════════════════════════════════════════════════╝",
        "",
    ])

    return "\n".join(lines)


def render_summary_table(history: list[PipelineMetrics]) -> str:
    """Render a summary table of multiple executions."""
    if not history:
        return "  No executions recorded."

    lines = [
        "  ┌─ Execution History ─────────────────────────────────────────────┐",
        "  │  #  Correlation   Duration  Confidence  Verdict   Escalation    │",
        "  ├─────────────────────────────────────────────────────────────────┤",
    ]

    for i, m in enumerate(history[-10:], 1):
        lines.append(
            f"  │  {i:<2} {m.correlation_id[:12]:<12} {m.total_duration_ms:>6.1f}ms  "
            f"{m.confidence_final:>8.3f}   {m.verification_verdict:<8}  {m.escalation_tier:<12} │"
        )

    lines.append("  └─────────────────────────────────────────────────────────────────┘")
    return "\n".join(lines)
