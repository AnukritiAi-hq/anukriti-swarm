"""``SwarmExecutionGraph`` + ``WorkflowGraphBuilder`` — queryable workflow graph.

Closes requirement #5 of the observability brief:

    nodes    = agents / tools
    edges    = workflow transitions
    metadata = timing / confidence / evidence

The existing ``visualization.graph.flow.render_flow_graph`` is
ASCII art only — great for CLI demos, useless for programmatic
analysis. This module produces a **proper graph object** that:

  - can be queried (``graph.nodes``, ``graph.edges``, ``graph.neighbors``)
  - serializes to a dict / Mermaid / Graphviz DOT
  - round-trips through MCP persistence

Construction
------------
The builder consumes the artifacts we already have — no new ingest
paths. Typical call:

    tracer = ExecutionTracer()
    tracer.ingest_orchestration_trace(trace)
    tracer.ingest_mcp_snapshot(snapshot)
    tracer.ingest_verification_traces(outcome.traces)

    builder = WorkflowGraphBuilder()
    graph = builder.build(
        tracer=tracer,
        activity=activity_monitor,   # optional but recommended
        profiler=profiler,           # optional
        outcome=verification_outcome,  # optional
    )

    print(graph.to_mermaid())

Nodes emerge from two sources: agent activations (the tracer's
AGENT_ACTIVATION events) and MCP tool-interaction events. Each is
a distinct node kind so dashboards can style them differently.

Edges emerge from:
  - the activity monitor's collaboration pairs
    (agent A → agent B when consecutive events belong to different
     agents)
  - explicit evidence lineage (retrieval trace → verification trace
    when they share a source_id)

Metadata attached per node: total_duration_ms, call_count,
utilization, failure_rate, last_seen. Per edge: count, kind,
first_seen timestamp.

Anti-goals
----------
This isn't a full graph algebra. No cycle detection, no shortest-
path, no traversal helpers — those can land if a caller asks.
Today the only consumer is the visualizer (commit 6) and the
cinematic player (commit 8), neither of which needs more than
nodes + edges + metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:  # pragma: no cover
    from agents.verification.agent import VerificationOutcome
    from observability.activity import AgentActivityMonitor
    from observability.profiler import TimingProfiler
    from observability.tracer import ExecutionTracer


NodeKind = Literal["agent", "tool", "verification", "system"]
EdgeKind = Literal["collaboration", "evidence", "verification"]


# ---------------------------------------------------------------------------
# Node / edge shapes
# ---------------------------------------------------------------------------


@dataclass
class GraphNode:
    """One node in the SwarmExecutionGraph."""

    id: str
    label: str
    kind: NodeKind
    call_count: int = 0
    total_duration_ms: float = 0.0
    utilization: float = 0.0
    failure_rate: float = 0.0
    last_seen: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "call_count": self.call_count,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "utilization": round(self.utilization, 4),
            "failure_rate": round(self.failure_rate, 4),
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "metadata": dict(self.metadata),
        }


@dataclass
class GraphEdge:
    """One directed edge in the graph."""

    source: str
    target: str
    kind: EdgeKind
    count: int = 1
    first_seen: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "kind": self.kind,
            "count": self.count,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


@dataclass
class SwarmExecutionGraph:
    """Queryable workflow graph: nodes=agents/tools, edges=transitions."""

    correlation_id: str = ""
    _nodes: dict[str, GraphNode] = field(default_factory=dict)
    _edges: list[GraphEdge] = field(default_factory=list)
    _edge_index: dict[tuple[str, str, str], GraphEdge] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Mutators (used by WorkflowGraphBuilder)
    # ------------------------------------------------------------------

    def add_node(self, node: GraphNode) -> GraphNode:
        existing = self._nodes.get(node.id)
        if existing is None:
            self._nodes[node.id] = node
            return node
        # Merge metrics — builder may see the same agent via multiple paths.
        existing.call_count = max(existing.call_count, node.call_count)
        existing.total_duration_ms = max(
            existing.total_duration_ms, node.total_duration_ms
        )
        existing.utilization = max(existing.utilization, node.utilization)
        existing.failure_rate = max(existing.failure_rate, node.failure_rate)
        if node.last_seen and (not existing.last_seen or node.last_seen > existing.last_seen):
            existing.last_seen = node.last_seen
        existing.metadata.update(node.metadata)
        return existing

    def add_edge(self, edge: GraphEdge) -> GraphEdge:
        key = (edge.source, edge.target, edge.kind)
        existing = self._edge_index.get(key)
        if existing is None:
            self._edge_index[key] = edge
            self._edges.append(edge)
            return edge
        existing.count += edge.count
        if edge.first_seen and (
            not existing.first_seen or edge.first_seen < existing.first_seen
        ):
            existing.first_seen = edge.first_seen
        existing.metadata.update(edge.metadata)
        return existing

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def nodes(self) -> list[GraphNode]:
        return list(self._nodes.values())

    @property
    def edges(self) -> list[GraphEdge]:
        return list(self._edges)

    def node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def neighbors(self, node_id: str) -> list[GraphNode]:
        """Return downstream nodes (edges out of node_id)."""
        targets = {e.target for e in self._edges if e.source == node_id}
        return [self._nodes[t] for t in targets if t in self._nodes]

    def predecessors(self, node_id: str) -> list[GraphNode]:
        sources = {e.source for e in self._edges if e.target == node_id}
        return [self._nodes[s] for s in sources if s in self._nodes]

    def summary(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
            "nodes_by_kind": self._count_by("kind", self._nodes.values()),
            "edges_by_kind": self._count_by("kind", self._edges),
        }

    @staticmethod
    def _count_by(attr: str, items: Any) -> dict[str, int]:
        out: dict[str, int] = {}
        for it in items:
            key = getattr(it, attr, "")
            out[key] = out.get(key, 0) + 1
        return out

    # ------------------------------------------------------------------
    # Serialization / export
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges],
            "summary": self.summary(),
        }

    def to_mermaid(self) -> str:
        """Render as a Mermaid flowchart for README / docs embedding.

        Node kinds get different shape syntax:
          agent        [brackets]
          tool         ([rounded])
          verification {diamond}
          system       (([cap]))

        Edge kinds map to different arrow styles:
          collaboration   solid arrow -->
          evidence        dotted arrow -..-
          verification    thick arrow ==>
        """
        lines = ["flowchart LR"]
        # Nodes — emit in sorted order for stable output.
        for n in sorted(self._nodes.values(), key=lambda x: x.id):
            shape_l, shape_r = {
                "agent": ("[", "]"),
                "tool": ("([", "])"),
                "verification": ("{", "}"),
                "system": ("((", "))"),
            }.get(n.kind, ("[", "]"))
            label = _escape_mermaid(n.label or n.id)
            metric = (
                f"<br/>{n.call_count} call(s)"
                if n.call_count
                else ""
            )
            lines.append(f"    {_mermaid_id(n.id)}{shape_l}\"{label}{metric}\"{shape_r}")

        # Edges.
        for e in self._edges:
            arrow = {
                "collaboration": "-->",
                "evidence": "-..->",
                "verification": "==>",
            }.get(e.kind, "-->")
            src = _mermaid_id(e.source)
            dst = _mermaid_id(e.target)
            label = f"|{e.count}|" if e.count > 1 else ""
            lines.append(f"    {src} {arrow}{label} {dst}")

        return "\n".join(lines)

    def to_dot(self) -> str:
        """Render as Graphviz DOT for offline rendering."""
        lines = ["digraph SwarmExecutionGraph {", '  rankdir="LR";']
        shape_map = {
            "agent": "box",
            "tool": "oval",
            "verification": "diamond",
            "system": "doublecircle",
        }
        for n in sorted(self._nodes.values(), key=lambda x: x.id):
            shape = shape_map.get(n.kind, "box")
            label = (n.label or n.id).replace('"', "'")
            lines.append(f'  "{n.id}" [shape={shape},label="{label}\\n({n.call_count} calls)"];')
        for e in self._edges:
            style = {
                "collaboration": "solid",
                "evidence": "dashed",
                "verification": "bold",
            }.get(e.kind, "solid")
            lines.append(
                f'  "{e.source}" -> "{e.target}" '
                f'[style={style},label="{e.count}"];'
            )
        lines.append("}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


@dataclass
class WorkflowGraphBuilder:
    """Constructs a SwarmExecutionGraph from tracer + optional collaborators.

    Stateless — one instance per build. Pass the tracer for raw
    events, activity monitor for utilization numbers, profiler for
    latency, and the verification outcome for evidence-lineage
    edges.
    """

    def build(
        self,
        *,
        tracer: "ExecutionTracer",
        activity: "AgentActivityMonitor | None" = None,
        profiler: "TimingProfiler | None" = None,
        outcome: "VerificationOutcome | None" = None,
        correlation_id: str = "",
    ) -> SwarmExecutionGraph:
        graph = SwarmExecutionGraph(
            correlation_id=correlation_id or tracer.correlation_id
        )

        # 1. Agent nodes + metrics from activity monitor (if supplied)
        #    otherwise derive from tracer events.
        self._add_agent_nodes(graph, tracer, activity)

        # 2. Tool nodes from MCP events.
        self._add_tool_nodes(graph, tracer, profiler)

        # 3. Collaboration edges from activity monitor; fall back to
        #    tracer-derived consecutive-event pairs.
        self._add_collaboration_edges(graph, tracer, activity)

        # 4. Evidence lineage edges from the verification outcome.
        if outcome is not None:
            self._add_evidence_edges(graph, outcome)

        return graph

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    def _add_agent_nodes(
        self,
        graph: SwarmExecutionGraph,
        tracer: "ExecutionTracer",
        activity: "AgentActivityMonitor | None",
    ) -> None:
        if activity is not None:
            for agent_id in activity.agents():
                a = activity.activity(agent_id)
                if a is None:
                    continue
                graph.add_node(
                    GraphNode(
                        id=agent_id,
                        label=agent_id,
                        kind="agent",
                        call_count=a.call_count,
                        total_duration_ms=a.total_duration_ms,
                        utilization=a.utilization(0.0),
                        failure_rate=a.failure_rate,
                        last_seen=a.last_seen,
                        metadata={"avg_gap_ms": a.avg_gap_ms},
                    )
                )
            return

        # No activity monitor — derive lightweight nodes from events.
        from observability.tracer import EventKind  # local import avoids cycle
        seen: dict[str, GraphNode] = {}
        for ev in tracer.events:
            if ev.kind != EventKind.AGENT_ACTIVATION:
                continue
            agent = ev.payload.get("agent_id") or ""
            if not agent:
                continue
            node = seen.get(agent) or GraphNode(id=agent, label=agent, kind="agent")
            node.call_count += 1
            if not node.last_seen or ev.timestamp > node.last_seen:
                node.last_seen = ev.timestamp
            seen[agent] = node
        for n in seen.values():
            graph.add_node(n)

    def _add_tool_nodes(
        self,
        graph: SwarmExecutionGraph,
        tracer: "ExecutionTracer",
        profiler: "TimingProfiler | None",
    ) -> None:
        from observability.tracer import EventKind
        for ev in tracer.events_by_kind(EventKind.MCP_INTERACTION):
            calls = int(ev.payload.get("calls", 1))
            failures = int(ev.payload.get("failures", 0))
            avg_latency = float(ev.payload.get("avg_latency_ms", 0.0))
            total_ms = avg_latency * calls
            fail_rate = (failures / calls) if calls else 0.0
            graph.add_node(
                GraphNode(
                    id=f"tool:{ev.name}",
                    label=ev.name,
                    kind="tool",
                    call_count=calls,
                    total_duration_ms=total_ms,
                    failure_rate=fail_rate,
                    last_seen=ev.timestamp,
                    metadata={"avg_latency_ms": avg_latency},
                )
            )

    def _add_collaboration_edges(
        self,
        graph: SwarmExecutionGraph,
        tracer: "ExecutionTracer",
        activity: "AgentActivityMonitor | None",
    ) -> None:
        if activity is not None:
            for (src, dst), count in activity.collaborations.items():
                graph.add_edge(
                    GraphEdge(
                        source=src,
                        target=dst,
                        kind="collaboration",
                        count=count,
                        first_seen=_first_ts(tracer, src),
                    )
                )
            return

        # Fallback: derive pairs from event order.
        last = ""
        for ev in tracer.events:
            agent = ev.payload.get("agent_id") or ""
            if not agent:
                continue
            if last and last != agent:
                graph.add_edge(
                    GraphEdge(
                        source=last,
                        target=agent,
                        kind="collaboration",
                        count=1,
                        first_seen=ev.timestamp,
                    )
                )
            last = agent

    def _add_evidence_edges(
        self,
        graph: SwarmExecutionGraph,
        outcome: "VerificationOutcome",
    ) -> None:
        """Connect generating_agent → tool nodes via evidence_refs."""
        for tr in outcome.traces:
            agent = getattr(tr, "generating_agent", "") or ""
            if not agent:
                continue
            # Make sure the generating agent node exists (even if the
            # activity monitor wasn't supplied).
            if graph.node(agent) is None:
                graph.add_node(GraphNode(id=agent, label=agent, kind="agent"))
            for source_id in getattr(tr, "evidence_refs", []) or []:
                evidence_node_id = f"evidence:{source_id}"
                if graph.node(evidence_node_id) is None:
                    graph.add_node(
                        GraphNode(
                            id=evidence_node_id,
                            label=source_id,
                            kind="system",
                            metadata={"source_id": source_id},
                        )
                    )
                graph.add_edge(
                    GraphEdge(
                        source=agent,
                        target=evidence_node_id,
                        kind="evidence",
                        count=1,
                        first_seen=getattr(tr, "created_at", None),
                        metadata={"claim_id": getattr(tr, "claim_id", "")},
                    )
                )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _first_ts(tracer: "ExecutionTracer", agent: str) -> datetime | None:
    """First timestamp where ``agent`` appeared in the tracer."""
    for ev in tracer.events:
        if ev.payload.get("agent_id") == agent or (
            ":" in ev.name and ev.name.split(":", 1)[1].strip() == agent
        ):
            return ev.timestamp
    return None


_MERMAID_SAFE: dict[int, str] = {
    ord(ch): f"_{ord(ch):x}_"
    for ch in [":", "-", ".", "/", " ", "[", "]", "(", ")", "{", "}", "=", ">"]
}


def _mermaid_id(raw: str) -> str:
    """Convert an agent/tool id into a Mermaid-safe node identifier."""
    return raw.translate(_MERMAID_SAFE) or "node"


def _escape_mermaid(label: str) -> str:
    """Escape characters that confuse Mermaid label parsing."""
    return label.replace('"', "'").replace("|", "/")


__all__ = [
    "SwarmExecutionGraph",
    "WorkflowGraphBuilder",
    "GraphNode",
    "GraphEdge",
    "NodeKind",
    "EdgeKind",
]
