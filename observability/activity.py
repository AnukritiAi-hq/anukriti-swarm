"""``AgentActivityMonitor`` — per-agent utilization + failure rate.

Closes the agent-utilization + failure-rate pieces of requirement
#8 of the observability brief. Complements ``TimingProfiler``:

    TimingProfiler       "how fast / how many tokens"
    AgentActivityMonitor "how busy / how reliable / who talked to whom"

Metrics tracked per agent
-------------------------

    call_count            total ingested events mentioning this agent
    success_count         events with status == 'success'
    failure_count         events with status == 'error'
    warning_count         events with status == 'warning'
    first_seen            timestamp of the first ingested event
    last_seen             timestamp of the most recent ingested event
    avg_gap_ms            mean gap between consecutive activations
                          (useful for detecting idle vs. busy agents)
    failure_rate          failure_count / call_count, [0.0, 1.0]
    utilization           agent.total_duration_ms / run_total_duration_ms
                          when a run duration is supplied; 0 otherwise

Collaboration graph
-------------------
The monitor also tracks pairwise agent-to-agent transitions — if
agent A emits an event, then agent B emits the next one, that's
one edge A → B. ``collaborations`` returns
``dict[tuple[str, str], int]`` for dashboards + the upcoming
``SwarmExecutionGraph``.

Usage
-----

    tracer = ExecutionTracer()
    monitor = AgentActivityMonitor()
    monitor.attach(tracer)

    # Ingest events through the tracer — monitor updates incrementally.
    tracer.ingest_orchestration_trace(trace)

    print(monitor.report(total_ms=result.total_duration_ms))

Stateful, thread-unsafe. One instance per run or session
(reset between sessions with ``reset()``).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from observability.tracer import ExecutionEvent, ExecutionTracer


# ---------------------------------------------------------------------------
# Per-agent snapshot
# ---------------------------------------------------------------------------


@dataclass
class AgentActivity:
    """Rolling metrics for one agent."""

    agent_id: str
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    warning_count: int = 0
    total_duration_ms: float = 0.0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    _gaps_ms: list[float] = field(default_factory=list)

    @property
    def failure_rate(self) -> float:
        if self.call_count == 0:
            return 0.0
        return round(self.failure_count / self.call_count, 4)

    @property
    def avg_gap_ms(self) -> float:
        if not self._gaps_ms:
            return 0.0
        return round(sum(self._gaps_ms) / len(self._gaps_ms), 2)

    def utilization(self, run_total_ms: float) -> float:
        """Fraction of a run's wall time this agent was active."""
        if run_total_ms <= 0:
            return 0.0
        return round(min(1.0, self.total_duration_ms / run_total_ms), 4)

    def to_dict(self, run_total_ms: float = 0.0) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "call_count": self.call_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "warning_count": self.warning_count,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "failure_rate": self.failure_rate,
            "avg_gap_ms": self.avg_gap_ms,
            "utilization": self.utilization(run_total_ms),
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------


@dataclass
class AgentActivityMonitor:
    """Rolling per-agent utilization + failure rate + collaboration graph.

    Stateful. Construct zero-arg; ``attach(tracer)`` subscribes and
    backfills existing events so the monitor starts with full
    history.
    """

    _by_agent: dict[str, AgentActivity] = field(default_factory=dict)
    # collaboration edge counts: (src_agent, dst_agent) -> count
    _collaborations: dict[tuple[str, str], int] = field(
        default_factory=lambda: defaultdict(int)
    )
    _last_agent: str = ""

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def attach(self, tracer: "ExecutionTracer") -> None:
        """Subscribe to a tracer; backfill existing events."""
        tracer.on_event(self._on_event)
        for ev in tracer.events:
            self._on_event(ev)

    # ------------------------------------------------------------------
    # Direct API (without a tracer)
    # ------------------------------------------------------------------

    def record(
        self,
        *,
        agent_id: str,
        status: str = "success",
        duration_ms: float = 0.0,
        timestamp: datetime | None = None,
    ) -> None:
        """Record one activation."""
        if not agent_id:
            return
        act = self._by_agent.get(agent_id)
        if act is None:
            act = AgentActivity(agent_id=agent_id)
            self._by_agent[agent_id] = act

        act.call_count += 1
        act.total_duration_ms += max(0.0, duration_ms)
        if status == "success":
            act.success_count += 1
        elif status == "error":
            act.failure_count += 1
        elif status == "warning":
            act.warning_count += 1

        if timestamp is not None:
            if act.first_seen is None:
                act.first_seen = timestamp
            if act.last_seen is not None:
                gap_ms = (timestamp - act.last_seen).total_seconds() * 1000
                if gap_ms >= 0:
                    act._gaps_ms.append(gap_ms)
            act.last_seen = timestamp

        # Collaboration edge from previous agent.
        if self._last_agent and self._last_agent != agent_id:
            self._collaborations[(self._last_agent, agent_id)] += 1
        self._last_agent = agent_id

    def reset(self) -> None:
        self._by_agent.clear()
        self._collaborations.clear()
        self._last_agent = ""

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def agents(self) -> list[str]:
        """Sorted list of agent ids seen so far."""
        return sorted(self._by_agent)

    def activity(self, agent_id: str) -> AgentActivity | None:
        return self._by_agent.get(agent_id)

    @property
    def collaborations(self) -> dict[tuple[str, str], int]:
        """Pairwise A→B edge counts (defensive-copied)."""
        return dict(self._collaborations)

    def total_agents(self) -> int:
        return len(self._by_agent)

    def busiest(self, n: int = 5) -> list[AgentActivity]:
        """Top-N agents by total_duration_ms."""
        return sorted(
            self._by_agent.values(),
            key=lambda a: a.total_duration_ms,
            reverse=True,
        )[:n]

    def most_failing(self, n: int = 5) -> list[AgentActivity]:
        """Top-N agents by absolute failure count (filter to count>0)."""
        with_failures = [a for a in self._by_agent.values() if a.failure_count > 0]
        return sorted(with_failures, key=lambda a: a.failure_count, reverse=True)[:n]

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def report(self, run_total_ms: float = 0.0) -> dict[str, Any]:
        """Compact dict report for dashboards / demos.

        ``run_total_ms`` is the total wall time of the enclosing
        orchestration run — used for utilization ratios. Omitted
        (0) → utilization reports 0 for every agent.
        """
        agents = sorted(
            self._by_agent.values(),
            key=lambda a: a.total_duration_ms,
            reverse=True,
        )
        return {
            "total_agents": self.total_agents(),
            "agents": [a.to_dict(run_total_ms) for a in agents],
            "collaborations": [
                {"from": src, "to": dst, "count": n}
                for (src, dst), n in sorted(
                    self._collaborations.items(), key=lambda kv: kv[1], reverse=True
                )
            ],
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_event(self, ev: "ExecutionEvent") -> None:
        """Tracer callback — extract agent, update counters."""
        agent_id = _derive_agent(ev)
        if not agent_id:
            return
        self.record(
            agent_id=agent_id,
            status=ev.status,
            duration_ms=float(ev.duration_ms or 0.0),
            timestamp=ev.timestamp,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_agent(ev: "ExecutionEvent") -> str:
    """Same shape as profiler._derive_agent but kept local to avoid
    an import cycle."""
    payload = ev.payload or {}
    agent = payload.get("agent_id")
    if isinstance(agent, str) and agent:
        return agent
    called = payload.get("called_by")
    if isinstance(called, str) and called:
        return called
    if ":" in ev.name:
        return ev.name.split(":", 1)[1].strip()
    return ""


__all__ = [
    "AgentActivityMonitor",
    "AgentActivity",
]
