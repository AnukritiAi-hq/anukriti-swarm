"""End-to-end LangGraph orchestration pipeline.

7-stage pharmacogenomic analysis:
  intake → orchestration → population → pharmacogene → retrieval → verification → narrative

Each stage is a deterministic node that transforms shared state.
Full execution trace and timing metrics are captured.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from workflows.nodes import (
    node_intake,
    node_narrative,
    node_orchestration,
    node_pharmacogene,
    node_population,
    node_retrieval,
    node_verification,
)


@dataclass
class StageMetrics:
    """Timing and metadata for a single pipeline stage."""

    stage: str
    duration_ms: float
    status: str  # "success", "warning", "error"
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineTrace:
    """Complete execution trace for a pipeline run."""

    correlation_id: str
    stages: list[StageMetrics] = field(default_factory=list)
    total_duration_ms: float = 0.0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    def add_stage(self, stage: str, duration_ms: float, status: str = "success", **details: Any) -> None:
        self.stages.append(StageMetrics(stage=stage, duration_ms=duration_ms, status=status, details=details))

    def summary(self) -> str:
        lines = [f"Pipeline Trace: {self.correlation_id}"]
        lines.append(f"  Total: {self.total_duration_ms:.1f}ms | Stages: {len(self.stages)}")
        lines.append("")
        for s in self.stages:
            icon = {"success": "✓", "warning": "⚠", "error": "✗"}[s.status]
            lines.append(f"  {icon} {s.stage:<20} {s.duration_ms:>7.1f}ms  {s.status}")
        return "\n".join(lines)


# Pipeline state type
PipelineState = dict[str, Any]

# Stage definitions (ordered)
STAGES = [
    ("intake", node_intake),
    ("orchestration", node_orchestration),
    ("population", node_population),
    ("pharmacogene", node_pharmacogene),
    ("retrieval", node_retrieval),
    ("verification", node_verification),
    ("narrative", node_narrative),
]


def run_pipeline(initial_state: PipelineState) -> tuple[PipelineState, PipelineTrace]:
    """Execute the full 7-stage pipeline with tracing.

    Each node receives the full state and returns partial updates.
    State accumulates through the pipeline. Timing is captured per stage.
    """
    correlation_id = initial_state.get("correlation_id") or uuid.uuid4().hex[:12]
    initial_state["correlation_id"] = correlation_id

    trace = PipelineTrace(correlation_id=correlation_id)
    state = dict(initial_state)
    pipeline_start = time.perf_counter()

    for stage_name, node_fn in STAGES:
        t0 = time.perf_counter()
        try:
            updates = node_fn(state)
            state.update(updates)
            duration = (time.perf_counter() - t0) * 1000
            status = "warning" if state.get("_stage_warning") else "success"
            state.pop("_stage_warning", None)
            trace.add_stage(stage_name, duration, status)
        except Exception as e:
            duration = (time.perf_counter() - t0) * 1000
            trace.add_stage(stage_name, duration, "error", error=str(e))
            state["errors"] = state.get("errors", []) + [f"[{stage_name}] {e}"]
            break

    trace.total_duration_ms = (time.perf_counter() - pipeline_start) * 1000
    trace.completed_at = datetime.now(timezone.utc)
    state["trace"] = trace

    return state, trace
