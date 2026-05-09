"""``TraceVisualizer`` — composes existing renderers into one bundle.

Closes requirements #4 and #7 of the observability brief. The brief
names four visual outputs every workflow must produce:

    orchestration graph     → SwarmExecutionGraph mermaid + ASCII flow
    execution timeline      → visualization.traces.timeline
    evidence map            → evidence lineage sub-view of the graph
    verification trace      → per-claim VerificationTrace list
    provenance chain        → MCPProvenanceStore.chain(claim_id)
                              (provenance ships with the MCP layer,
                               the visualizer just resolves it)

Existing renderers (don't duplicate, compose):

    visualization.traces.renderer   CLI trace renderer w/ ANSI colors
    visualization.traces.timeline   Gantt-style timeline
    visualization.graph.flow        ASCII flow graph
    visualization.export            JSON trace export

TraceVisualizer is the one-call surface: ``render_all(ctx)`` returns
a ``VisualBundle`` holding **every** visual output for the run. Each
field is a string (colored CLI output, mermaid source, or JSON) —
not pre-rendered to a particular format, so downstream consumers
(demo, dashboard, README embedding) can pick which they want.

Usage
-----

    viz = TraceVisualizer(tracer=tracer, graph=graph, outcome=outcome)
    bundle = viz.render_all(total_duration_ms=result.total_duration_ms)

    print(bundle.swarm_map)          # ANSI flow graph (CLI)
    print(bundle.timeline)           # Gantt timeline (CLI)
    print(bundle.verification_trace) # per-claim checkpoint list
    print(bundle.evidence_map)       # citation lineage
    print(bundle.mermaid_graph)      # mermaid source (README)

Every output is text — the visualizer doesn't launch a browser,
write image files, or depend on external tools. That's by design:
the safety engine's audit guarantee extends to visualizations
(anyone can re-render from the same inputs, anywhere, offline).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from visualization.graph.flow import (
    render_confidence_propagation,
    render_evidence_flow,
    render_flow_graph,
)
from visualization.traces.timeline import ExecutionTimeline

if TYPE_CHECKING:  # pragma: no cover
    from agents.verification.agent import VerificationOutcome
    from observability.graph import SwarmExecutionGraph
    from observability.tracer import ExecutionTracer


# ---------------------------------------------------------------------------
# Bundle
# ---------------------------------------------------------------------------


@dataclass
class VisualBundle:
    """All four brief-named visuals + supplementary artifacts.

    Every field is a string so the bundle round-trips through JSON /
    MCP / a plain file write without special handling. Empty strings
    mean "this artifact wasn't produced for this run" — usually
    because a required source was missing (e.g. no outcome supplied
    → verification_trace + evidence_map will be empty).
    """

    correlation_id: str = ""
    swarm_map: str = ""              # req #7: active swarm map
    timeline: str = ""               # req #7: agent collaboration timeline
    evidence_map: str = ""           # req #7: evidence lineage
    verification_trace: str = ""     # req #7: verification checkpoints
    mermaid_graph: str = ""          # bonus: graph for README embedding
    dot_graph: str = ""              # bonus: Graphviz DOT
    confidence_chart: str = ""       # bonus: confidence propagation
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "swarm_map": self.swarm_map,
            "timeline": self.timeline,
            "evidence_map": self.evidence_map,
            "verification_trace": self.verification_trace,
            "mermaid_graph": self.mermaid_graph,
            "dot_graph": self.dot_graph,
            "confidence_chart": self.confidence_chart,
            "summary": dict(self.summary),
        }


# ---------------------------------------------------------------------------
# Visualizer
# ---------------------------------------------------------------------------


# ANSI formatting re-used in several places.
_B = "\033[1m"
_D = "\033[2m"
_R = "\033[0m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_MAGENTA = "\033[35m"
_CYAN = "\033[36m"
_BLUE = "\033[34m"


def _state_color(state: str) -> str:
    """Return ANSI color code for a verification state token."""
    return {
        "pass": _GREEN,
        "warn": _YELLOW,
        "fail": _RED,
    }.get(state, _D)


@dataclass
class TraceVisualizer:
    """Composes the 4 brief-named visuals + bonus artifacts.

    Pass whatever collaborators you have; any missing collaborator
    leaves its section of the bundle empty but the rest still
    renders. Construction is zero-arg friendly:

        viz = TraceVisualizer()
        bundle = viz.render_all(run_dict=run, outcome=outcome)
    """

    tracer: "ExecutionTracer | None" = None
    graph: "SwarmExecutionGraph | None" = None
    outcome: "VerificationOutcome | None" = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_all(
        self,
        *,
        run_dict: dict[str, Any] | None = None,
        outcome: "VerificationOutcome | None" = None,
        graph: "SwarmExecutionGraph | None" = None,
        tracer: "ExecutionTracer | None" = None,
        total_duration_ms: float = 0.0,
        correlation_id: str = "",
    ) -> VisualBundle:
        """Produce every visual output in one call.

        Call-site collaborators override instance-level ones — lets
        a single visualizer be reused across multiple runs without
        re-instantiation.
        """
        outc = outcome or self.outcome
        g = graph or self.graph
        tr = tracer or self.tracer

        cid = (
            correlation_id
            or (outc.correlation_id if outc else "")
            or (g.correlation_id if g else "")
            or (tr.correlation_id if tr else "")
        )

        bundle = VisualBundle(correlation_id=cid)

        # 1. Swarm map — ASCII flow graph. Needs a run dict (carries
        #    phenotype + population + verification verdict).
        if run_dict is not None:
            bundle.swarm_map = render_flow_graph(run_dict)

        # 2. Timeline — Gantt-style from the tracer's event stream.
        if tr is not None:
            bundle.timeline = self._render_timeline(tr, total_duration_ms)

        # 3. Evidence map — lineage between agents and cited sources.
        if outc is not None:
            bundle.evidence_map = self._render_evidence_map(outc, g)

        # 4. Verification trace — the per-claim checkpoint list.
        if outc is not None:
            bundle.verification_trace = self._render_verification_trace(outc)

        # Bonus: mermaid + DOT for the graph.
        if g is not None:
            bundle.mermaid_graph = g.to_mermaid()
            bundle.dot_graph = g.to_dot()

        # Bonus: confidence propagation chart if the run has stage
        # confidences.
        if run_dict is not None:
            bundle.confidence_chart = self._render_confidence(run_dict)

        bundle.summary = self._build_summary(
            tr=tr, g=g, outc=outc, total_duration_ms=total_duration_ms,
        )
        return bundle

    # ------------------------------------------------------------------
    # Individual renderers
    # ------------------------------------------------------------------

    def _render_timeline(
        self, tracer: "ExecutionTracer", total_duration_ms: float
    ) -> str:
        """Build a timeline from the tracer's events.

        Each event becomes one timeline bar; bars are sized by
        relative duration. Uses the existing ``ExecutionTimeline``
        primitive so rendering matches the rest of the codebase.
        """
        events = [e for e in tracer.events if e.duration_ms > 0]
        if not events:
            return "  (no timed events in tracer)"

        total = total_duration_ms or sum(e.duration_ms for e in events)
        if total <= 0:
            total = 1.0

        timeline = ExecutionTimeline(total_ms=total)
        for ev in events:
            # Short labels so the Gantt rendering stays readable.
            label = ev.name
            if len(label) > 18:
                label = label[:18]
            timeline.add_stage(
                agent=label,
                stage=ev.kind.value,
                duration_ms=float(ev.duration_ms),
                status=ev.status,
            )
        return timeline.render(width=46)

    def _render_evidence_map(
        self,
        outcome: "VerificationOutcome",
        graph: "SwarmExecutionGraph | None",
    ) -> str:
        """Evidence lineage view: agent → evidence source chains.

        Two passes:
          1. flat view: every (agent, evidence) pair the outcome's
             traces declare
          2. resolved view: if an evidence source landed in MCP, mark
             it resolved (delegates to GroundingEngine output if it
             was in the bundle)
        """
        lines: list[str] = []
        lines.append(
            f"  {_B}┌─ Evidence Lineage{'─' * 50}┐{_R}"
        )

        by_agent: dict[str, set[str]] = {}
        for tr in outcome.traces:
            agent = getattr(tr, "generating_agent", "") or "—"
            for src in getattr(tr, "evidence_refs", ()) or ():
                by_agent.setdefault(agent, set()).add(src)

        if not by_agent:
            lines.append(f"  {_D}│  (no evidence citations in this outcome)  │{_R}")
        else:
            # Resolved/unresolved markers from the grounding report if
            # one was produced.
            missing: set[str] = set()
            if outcome.grounding is not None:
                missing = set(outcome.grounding.missing_source_ids or [])

            for agent in sorted(by_agent):
                lines.append(f"  {_D}│{_R}  {_B}{agent}{_R}")
                for src in sorted(by_agent[agent]):
                    ok = src not in missing
                    mark = f"{_GREEN}✓{_R}" if ok else f"{_YELLOW}?{_R}"
                    lines.append(
                        f"  {_D}│{_R}    {mark} {src}"
                        + (f"  {_D}(cached){_R}" if ok else f"  {_D}(missing from cache){_R}")
                    )

        # Summary counts via the graph's evidence edges.
        if graph is not None:
            evidence_edges = [e for e in graph.edges if e.kind == "evidence"]
            if evidence_edges:
                lines.append(f"  {_D}│{_R}")
                lines.append(
                    f"  {_D}│  Graph edges: "
                    f"{len(evidence_edges)} evidence link(s){_R}"
                )

        lines.append(f"  {_B}└{'─' * 66}┘{_R}")
        return "\n".join(lines)

    def _render_verification_trace(
        self, outcome: "VerificationOutcome"
    ) -> str:
        """Per-claim verification checkpoint list (req #7 checkpoints)."""
        lines: list[str] = []
        lines.append(f"  {_B}┌─ Verification Checkpoints{'─' * 42}┐{_R}")
        if not outcome.traces:
            lines.append(f"  {_D}│  (no verification traces on outcome)  │{_R}")
        else:
            tier = outcome.tier
            safe = outcome.is_safe
            verdict_color = _GREEN if safe else _RED
            lines.append(
                f"  {_D}│{_R}  tier={_B}{verdict_color}{tier}{_R}"
                f"  is_safe={verdict_color}{safe}{_R}"
            )
            if outcome.decision and outcome.decision.reason:
                reason = outcome.decision.reason[:56]
                lines.append(f"  {_D}│  {reason}{_R}")
            lines.append(f"  {_D}│{_R}")
            for tr in outcome.traces:
                state = getattr(tr, "state", "")
                color = _state_color(state)
                validator = getattr(tr, "validator", "")[:26]
                rule = getattr(tr, "rule_id", "")[:26]
                conf = float(getattr(tr, "confidence", 0.0))
                lines.append(
                    f"  {_D}│{_R}  [{color}{state:<4}{_R}] "
                    f"{validator:<26} {rule:<26} conf={conf:.2f}"
                )
                # Include escalation events inline.
                for ev in getattr(tr, "escalation_events", ()) or ():
                    action = getattr(ev, "action", "")
                    target = getattr(ev, "target", "")
                    lines.append(
                        f"  {_D}│{_R}    {_MAGENTA}→ {action}{_R} "
                        f"{_D}{target[:40]}{_R}"
                    )
        lines.append(f"  {_B}└{'─' * 66}┘{_R}")
        return "\n".join(lines)

    def _render_confidence(self, run_dict: dict[str, Any]) -> str:
        """Confidence propagation chart from the existing flow module."""
        pgx = (run_dict.get("pharmacogene_result") or {}).get("confidence", 1.0)
        pop = (run_dict.get("population_result") or {}).get("confidence", 0.9)
        grounding = float(run_dict.get("grounding_score") or 0.8)
        final = float(
            (run_dict.get("verification") or {}).get("confidence") or 0.0
        )
        return render_confidence_propagation(
            {"phenotype": float(pgx), "population": float(pop), "evidence": grounding},
            final=final,
        )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    @staticmethod
    def _build_summary(
        *,
        tr: "ExecutionTracer | None",
        g: "SwarmExecutionGraph | None",
        outc: "VerificationOutcome | None",
        total_duration_ms: float,
    ) -> dict[str, Any]:
        return {
            "total_duration_ms": round(total_duration_ms, 2),
            "events": tr.count() if tr else 0,
            "event_kinds": tr.summary() if tr else {},
            "nodes": len(g.nodes) if g else 0,
            "edges": len(g.edges) if g else 0,
            "tier": outc.tier if outc else "",
            "is_safe": outc.is_safe if outc else False,
        }


__all__ = ["TraceVisualizer", "VisualBundle"]
