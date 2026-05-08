"""Orchestration trace primitives.

Structured observability for the orchestration layer. These are plain
dataclasses (not Pydantic) because they are hot-path and append-only;
Pydantic validation would add needless overhead here. Serialization is
handled explicitly via ``to_dict``.

Three nested concepts:

``StepMetric``
    One unit of orchestration work (e.g. "route to pharmacogene_cyp2c19",
    "call Gemini planner"). Captures what happened, how long it took,
    and whether it was deterministic or generative.

``ActivationLog``
    Record that a specific specialist agent was activated by the router.
    Independent of ``StepMetric`` so activation history can be inspected
    without walking the full step list.

``OrchestrationTrace``
    The top-level, per-run trace. Holds the ordered ``steps``,
    ``activations``, high-level ``reasoning_summary`` produced by Gemini
    (optional), and timing metadata.

All of these are safe to serialize to JSON for the MongoDB MCP trace
store or for ``visualization.export`` JSON dumps.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

# Origin tag aligns with the deterministic/generative boundary.
# Anything that can touch an LLM must be tagged ``"generative"``;
# everything else is ``"deterministic"``.
Origin = Literal["deterministic", "generative"]

# Status of a single orchestration step.
StepStatus = Literal["success", "warning", "error", "skipped"]


@dataclass
class StepMetric:
    """One orchestration step — a single unit of coordination work.

    Examples:
      - "plan"                (origin=generative, planner decomposed query)
      - "route:pharmacogene"  (origin=deterministic, router selected agent)
      - "execute:cyp2c19"     (origin=deterministic, agent ran)
      - "synthesize"          (origin=generative, narrative summary)
    """

    step: int
    name: str
    origin: Origin
    status: StepStatus = "success"
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["started_at"] = self.started_at.isoformat()
        return d


@dataclass
class ActivationLog:
    """Record that a specialist agent was activated.

    Kept separate from ``StepMetric`` so a caller can ask "which agents
    did this orchestration touch?" without scanning every step.
    """

    agent_id: str
    role: str  # e.g. "pharmacogene", "population", "retrieval", "verification"
    reason: str  # why the router picked this agent
    activated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["activated_at"] = self.activated_at.isoformat()
        return d


@dataclass
class OrchestrationTrace:
    """Top-level trace for one orchestration run.

    Captures planning, routing, activation, execution, and synthesis.
    Pair with the existing ``workflows.pipeline.PipelineTrace`` for
    stage-level timing of the deterministic sub-pipeline — this trace
    lives *one level above* that: the deterministic pipeline is a single
    ``StepMetric`` named ``"pipeline"`` inside this trace.
    """

    correlation_id: str
    query: str = ""
    steps: list[StepMetric] = field(default_factory=list)
    activations: list[ActivationLog] = field(default_factory=list)
    reasoning_summary: str = ""  # Gemini-produced plan/summary (optional)
    total_duration_ms: float = 0.0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    # --- mutation helpers (append-only) ---

    def record_step(
        self,
        name: str,
        origin: Origin,
        duration_ms: float,
        status: StepStatus = "success",
        **details: Any,
    ) -> StepMetric:
        """Append a new step and return it."""
        metric = StepMetric(
            step=len(self.steps) + 1,
            name=name,
            origin=origin,
            status=status,
            duration_ms=duration_ms,
            details=details,
        )
        self.steps.append(metric)
        return metric

    def record_activation(self, agent_id: str, role: str, reason: str) -> ActivationLog:
        """Log that an agent was activated."""
        log = ActivationLog(agent_id=agent_id, role=role, reason=reason)
        self.activations.append(log)
        return log

    def mark_complete(self, total_duration_ms: float) -> None:
        """Finalize the trace."""
        self.total_duration_ms = total_duration_ms
        self.completed_at = datetime.now(timezone.utc)

    # --- introspection ---

    @property
    def activated_agents(self) -> list[str]:
        """De-duplicated list of activated agent IDs in activation order."""
        seen: set[str] = set()
        ordered: list[str] = []
        for a in self.activations:
            if a.agent_id not in seen:
                seen.add(a.agent_id)
                ordered.append(a.agent_id)
        return ordered

    def generative_steps(self) -> list[StepMetric]:
        return [s for s in self.steps if s.origin == "generative"]

    def deterministic_steps(self) -> list[StepMetric]:
        return [s for s in self.steps if s.origin == "deterministic"]

    def summary(self) -> str:
        """One-line-per-step human-readable summary (useful in demos)."""
        icon = {"success": "✓", "warning": "⚠", "error": "✗", "skipped": "·"}
        lines = [
            f"OrchestrationTrace {self.correlation_id}",
            f"  query: {self.query or '—'}",
            f"  total: {self.total_duration_ms:.1f}ms | "
            f"steps: {len(self.steps)} (det={len(self.deterministic_steps())}, "
            f"gen={len(self.generative_steps())}) | "
            f"agents: {len(self.activated_agents)}",
        ]
        for s in self.steps:
            lines.append(
                f"  {icon[s.status]} #{s.step:02d} {s.name:<32} "
                f"[{s.origin[:3]}] {s.duration_ms:>7.1f}ms"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "query": self.query,
            "steps": [s.to_dict() for s in self.steps],
            "activations": [a.to_dict() for a in self.activations],
            "reasoning_summary": self.reasoning_summary,
            "total_duration_ms": self.total_duration_ms,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


__all__ = ["Origin", "StepStatus", "StepMetric", "ActivationLog", "OrchestrationTrace"]
