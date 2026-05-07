"""Execution metrics collection and agent activity tracking.

Collects per-stage and per-agent metrics from pipeline executions:
- Latency (per stage, total)
- Agent participation
- Confidence changes through pipeline
- Evidence quality (grounding score, citation count)
- Verification outcomes
- Escalation events

Future: OpenTelemetry-compatible metric export.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from workflows.pipeline import PipelineTrace


@dataclass
class AgentMetrics:
    """Metrics for a single agent's participation."""

    agent_id: str
    duration_ms: float
    status: str
    confidence_in: float | None = None
    confidence_out: float | None = None


@dataclass
class PipelineMetrics:
    """Aggregated metrics for a pipeline execution."""

    correlation_id: str
    total_duration_ms: float
    stage_count: int
    agents_participated: list[str]
    stages: list[AgentMetrics]

    # Quality metrics
    grounding_score: float = 0.0
    citation_count: int = 0
    verification_verdict: str = ""
    confidence_final: float = 0.0
    escalation_tier: str = ""

    # Composition
    deterministic_stages: int = 0
    generative_stages: int = 0


class MetricsCollector:
    """Collects and aggregates execution metrics."""

    def __init__(self) -> None:
        self._history: list[PipelineMetrics] = []

    def collect(self, state: dict[str, Any], trace: PipelineTrace) -> PipelineMetrics:
        """Collect metrics from a completed pipeline execution."""
        stages = [
            AgentMetrics(agent_id=s.stage, duration_ms=s.duration_ms, status=s.status)
            for s in trace.stages
        ]

        v = state.get("verification", {})
        pgx = state.get("pharmacogene_result", {})

        metrics = PipelineMetrics(
            correlation_id=trace.correlation_id,
            total_duration_ms=trace.total_duration_ms,
            stage_count=len(trace.stages),
            agents_participated=[s.stage for s in trace.stages],
            stages=stages,
            grounding_score=state.get("grounding_score", 0.0),
            citation_count=len(state.get("citations", [])),
            verification_verdict=v.get("verdict", ""),
            confidence_final=v.get("confidence", 0.0),
            escalation_tier=v.get("escalation_tier", ""),
            deterministic_stages=sum(1 for s in trace.stages if s.stage != "narrative"),
            generative_stages=1 if "narrative" in [s.stage for s in trace.stages] else 0,
        )

        self._history.append(metrics)
        return metrics

    @property
    def history(self) -> list[PipelineMetrics]:
        return list(self._history)

    def summary(self) -> dict[str, Any]:
        """Aggregate summary across all collected executions."""
        if not self._history:
            return {"executions": 0}

        total = len(self._history)
        avg_duration = sum(m.total_duration_ms for m in self._history) / total
        avg_confidence = sum(m.confidence_final for m in self._history) / total
        pass_rate = sum(1 for m in self._history if m.verification_verdict == "pass") / total

        return {
            "executions": total,
            "avg_duration_ms": round(avg_duration, 2),
            "avg_confidence": round(avg_confidence, 3),
            "verification_pass_rate": round(pass_rate, 3),
            "avg_citations": round(sum(m.citation_count for m in self._history) / total, 1),
            "avg_grounding": round(sum(m.grounding_score for m in self._history) / total, 3),
        }
