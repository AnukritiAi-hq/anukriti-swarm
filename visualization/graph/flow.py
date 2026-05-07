"""Agent interaction and evidence flow visualization.

Renders the execution graph showing how data flows between agents,
with markers for deterministic vs generative boundaries.
"""

from __future__ import annotations

from typing import Any


def render_flow_graph(state: dict[str, Any]) -> str:
    """Render the agent interaction flow as ASCII art."""
    pgx = state.get("pharmacogene_result", {})
    pop = state.get("population_result", {})
    verification = state.get("verification", {})
    phenotype = pgx.get("phenotype", "?")
    risk = pgx.get("risk", "?")
    freq = pop.get("frequency", "?")
    verdict = verification.get("verdict", "?")
    conf = verification.get("confidence", 0)

    lines = [
        "  ┌─ Agent Flow Graph ──────────────────────────────────────────────┐",
        "  │                                                                  │",
        "  │   ┌──────────────┐                                              │",
        "  │   │ ORCHESTRATOR │─── dispatch ──┐                              │",
        "  │   └──────────────┘               │                              │",
        "  │          │                       │                              │",
        "  │          ▼                       ▼                              │",
        "  │   ┌──────────────┐     ┌──────────────────┐                    │",
        f"  │   │  POPULATION  │     │  PHARMACOGENE    │                    │",
        f"  │   │  freq={str(freq):<6}│     │  {phenotype:<16} │                    │",
        "  │   └──────┬───────┘     └────────┬─────────┘                    │",
        "  │          │                      │                              │",
        "  │          └──────────┬───────────┘                              │",
        "  │                     ▼                                          │",
        "  │          ┌─────────────────────┐                               │",
        "  │          │     RETRIEVAL       │ ◀── evidence grounding        │",
        "  │          └──────────┬──────────┘                               │",
        "  │                     │                                          │",
        "  │   ╔═══════════════════════════════╗  ◀── DET/GEN BOUNDARY     │",
        "  │                     ▼                                          │",
        "  │          ┌─────────────────────┐                               │",
        f"  │          │   VERIFICATION      │  verdict={verdict:<4} conf={conf:.2f}  │",
        "  │          └──────────┬──────────┘                               │",
        "  │                     ▼                                          │",
        "  │          ┌─────────────────────┐                               │",
        f"  │          │    NARRATIVE        │  risk={risk:<12}         │",
        "  │          └─────────────────────┘                               │",
        "  │                                                                  │",
        "  └──────────────────────────────────────────────────────────────────┘",
    ]
    return "\n".join(lines)


def render_evidence_flow(citations: list[str], grounding_score: float) -> str:
    """Render evidence flow from sources to claims."""
    lines = [
        "  ┌─ Evidence Flow ─────────────────────────────────────────────────┐",
        "  │                                                                  │",
    ]
    for cit in citations[:5]:
        lines.append(f"  │   📄 {cit:<55}     │")
    lines.extend([
        "  │       │                                                          │",
        "  │       ▼                                                          │",
        f"  │   ┌─ Grounding: {'█' * int(grounding_score * 20)}{'░' * (20 - int(grounding_score * 20))} {grounding_score:.0%} ─┐              │",
        "  │   │  Every claim → citation → source document  │              │",
        "  │   └────────────────────────────────────────────┘              │",
        "  │                                                                  │",
        "  └──────────────────────────────────────────────────────────────────┘",
    ])
    return "\n".join(lines)


def render_confidence_propagation(stages: dict[str, float], final: float) -> str:
    """Render confidence propagation through pipeline stages."""
    lines = [
        "  ┌─ Confidence Propagation ───────────────────────────────────────┐",
        "  │                                                                  │",
    ]
    for stage, conf in stages.items():
        bar = "█" * int(conf * 15) + "░" * (15 - int(conf * 15))
        lines.append(f"  │   {stage:<15} {bar} {conf:.3f}                       │")
    lines.extend([
        "  │                     ×                                            │",
        f"  │   {'FINAL':<15} {'█' * int(final * 15)}{'░' * (15 - int(final * 15))} {final:.3f}  ◀── propagated      │",
        "  │                                                                  │",
        "  └──────────────────────────────────────────────────────────────────┘",
    ])
    return "\n".join(lines)
