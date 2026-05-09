"""Anukriti Swarm — production observability + visualization layer.

Composes the existing tracing, metrics, and visualization primitives
into the five public classes the observability brief names, plus a
queryable ``SwarmExecutionGraph``. This package is **additive** —
nothing in the existing observability stack changes its behaviour.

Layered on top of:

    core.orchestrator.trace     OrchestrationTrace / StepMetric
    integrations.mcp.models     MCPObservability / tool-call metrics
    core.verification.trace     VerificationTrace
    workflows.pipeline          PipelineTrace (deterministic sub-pipeline)
    metrics.collector           MetricsCollector / PipelineMetrics
    tracing.telemetry           TelemetrySpan / JSONL export
    visualization/              renderer + timeline + flow + export

Public surface (lands in follow-up commits, one per class):

    ExecutionTracer          unified event stream across 7 kinds
                             (activation, routing, retrieval,
                              verification, MCP, Gemini, rule)
    AgentActivityMonitor     per-agent utilization + failure rate
    WorkflowGraphBuilder     constructs SwarmExecutionGraph
    TraceVisualizer          renders the 4 brief-named visuals
    TimingProfiler           latency distribution + token usage

    SwarmExecutionGraph      nodes=agents/tools, edges=transitions,
                             metadata=timing/confidence/evidence

    TraceReplayer            rehydrate + replay a past run
    FailureAnalyzer          group fail events, surface hotspots
    CinematicPlayer          presentation mode

Design principles:

1. **Non-destructive.** All existing demos, imports, and tools keep
   working unchanged. New classes *compose* existing primitives.
2. **Stream-oriented.** ExecutionTracer is the single event source;
   every other class consumes its stream. Easy to add new analytics
   by subscribing.
3. **Serializable everywhere.** Every dataclass has a to_dict() that
   round-trips through MCP or JSON dashboards.
4. **Production-oriented.** No LLM in the hot path; pure functions
   for profiling + graph construction; p95/p99 latency helpers.
"""

from __future__ import annotations

from observability.tracer import (
    EventHandler,
    EventKind,
    ExecutionEvent,
    ExecutionTracer,
)
from observability.profiler import (
    LatencyDistribution,
    TimingProfiler,
    TokenUsage,
)
from observability.activity import AgentActivity, AgentActivityMonitor
from observability.graph import (
    EdgeKind,
    GraphEdge,
    GraphNode,
    NodeKind,
    SwarmExecutionGraph,
    WorkflowGraphBuilder,
)
from observability.visualizer import TraceVisualizer, VisualBundle
from observability.replay import FailureAnalyzer, FailureSummary, TraceReplayer
from observability.cinematic import CinematicConfig, CinematicPlayer, NarratorHook

__all__: list[str] = [
    # Tracer
    "ExecutionTracer",
    "ExecutionEvent",
    "EventKind",
    "EventHandler",
    # Profiler
    "TimingProfiler",
    "LatencyDistribution",
    "TokenUsage",
    # Activity
    "AgentActivityMonitor",
    "AgentActivity",
    # Graph
    "SwarmExecutionGraph",
    "WorkflowGraphBuilder",
    "GraphNode",
    "GraphEdge",
    "NodeKind",
    "EdgeKind",
    # Visualizer
    "TraceVisualizer",
    "VisualBundle",
    # Replay + failure
    "TraceReplayer",
    "FailureAnalyzer",
    "FailureSummary",
    # Cinematic
    "CinematicPlayer",
    "CinematicConfig",
    "NarratorHook",
]
