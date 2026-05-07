"""Anukriti Swarm — LangGraph-style graph runner.

A lightweight DAG execution engine that mimics LangGraph's StateGraph pattern:
- Nodes are callable agents that transform shared state
- Edges define execution order and conditional routing
- State flows through the graph, accumulating results

Future: Will be replaced by actual LangGraph StateGraph when
the project moves to production-grade orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from agents.logging import ExecutionTrace, trace_agent
from agents.state import SwarmState


# Type alias for a graph node function
NodeFn = Callable[[SwarmState], SwarmState]


@dataclass
class Edge:
    """A directed edge in the execution graph."""

    source: str
    target: str
    condition: Callable[[SwarmState], bool] | None = None  # None = unconditional


@dataclass
class GraphNode:
    """A node in the execution graph wrapping an agent or function."""

    name: str
    fn: NodeFn
    parallel_group: str | None = None  # Nodes in same group run "in parallel"


class StateGraph:
    """LangGraph-style state graph for agent orchestration.

    Builds a DAG of agent nodes connected by edges. Executes nodes
    in topological order, passing shared state through each node.

    Usage:
        graph = StateGraph()
        graph.add_node("orchestrator", orchestrator_agent)
        graph.add_node("chr_analysis", chromosome_agent)
        graph.add_edge("orchestrator", "chr_analysis")
        result = graph.run(initial_state, trace)
    """

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[Edge] = []
        self.entry_point: str | None = None

    def add_node(self, name: str, fn: NodeFn, parallel_group: str | None = None) -> None:
        """Add a named node (agent) to the graph."""
        self.nodes[name] = GraphNode(name=name, fn=fn, parallel_group=parallel_group)

    def add_edge(
        self, source: str, target: str, condition: Callable[[SwarmState], bool] | None = None
    ) -> None:
        """Add a directed edge between nodes. Optional condition for routing."""
        self.edges.append(Edge(source=source, target=target, condition=condition))

    def set_entry_point(self, name: str) -> None:
        """Set the starting node of the graph."""
        self.entry_point = name

    def run(self, state: SwarmState, trace: ExecutionTrace) -> SwarmState:
        """Execute the graph in topological order.

        Nodes are executed sequentially following edges. Conditional edges
        are evaluated at runtime — if condition returns False, the edge is skipped.
        """
        if not self.entry_point:
            raise ValueError("No entry point set. Call set_entry_point() first.")

        visited: set[str] = set()
        execution_order = self._resolve_order()

        for node_name in execution_order:
            node = self.nodes[node_name]

            # Check if any incoming conditional edge blocks this node
            if not self._should_execute(node_name, state):
                trace.add(node_name, "skip", "conditional_edge_false")
                continue

            with trace_agent(trace, node_name, stage=node_name):
                updates = node.fn(state)
                if updates:
                    state = {**state, **updates}  # type: ignore[assignment]
                visited.add(node_name)

        return state

    def _resolve_order(self) -> list[str]:
        """Resolve execution order via topological sort."""
        in_degree: dict[str, int] = {name: 0 for name in self.nodes}
        adjacency: dict[str, list[str]] = {name: [] for name in self.nodes}

        for edge in self.edges:
            adjacency[edge.source].append(edge.target)
            in_degree[edge.target] += 1

        # Start with entry point, then BFS
        queue = [self.entry_point] if self.entry_point else []
        order: list[str] = []

        # Simple topological sort
        zero_in = [n for n, d in in_degree.items() if d == 0]
        if self.entry_point and self.entry_point in zero_in:
            queue = [self.entry_point]
        else:
            queue = zero_in

        visited: set[str] = set()
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            order.append(node)
            for neighbor in adjacency.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return order

    def _should_execute(self, node_name: str, state: SwarmState) -> bool:
        """Check if all conditional edges targeting this node pass."""
        for edge in self.edges:
            if edge.target == node_name and edge.condition:
                if not edge.condition(state):
                    return False
        return True
