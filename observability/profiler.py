"""``TimingProfiler`` — latency distribution + token usage.

Closes part of requirement #8 of the observability brief (
orchestration / verification / retrieval latency + token usage +
failure rate).

What makes this different from ``metrics.collector.MetricsCollector``?
MetricsCollector aggregates per-run metrics for dashboards —
one row per pipeline execution. The profiler sits at a finer
grain: **per-stage latency distributions** (p50 / p95 / p99),
**per-agent timing**, and **token usage** across Gemini / OpenAI
calls. Data to answer "which stage is slow?" and "how many tokens
did we burn this session?".

Design
------
Profiling is **stream-oriented**. Feed it an ``ExecutionTracer``
subscription and latency/token counters update incrementally:

    tracer = ExecutionTracer()
    profiler = TimingProfiler()
    profiler.attach(tracer)

    # Now ingest events; the profiler updates automatically.
    tracer.ingest_orchestration_trace(trace)

    print(profiler.latency_report())
    print(profiler.token_report())

Can also be used standalone (``profiler.record(...)`` + ``.record_tokens(...)``)
without a tracer — useful for tests + probes.

Percentiles are computed by ``statistics.quantiles`` when the
sample is large enough (n >= 10) and fall back to raw values for
smaller samples.

Token usage
-----------
The codebase doesn't persist token counts today — LLM calls flow
through ``ai.gemini.client.AIClient`` but usage isn't recorded.
Rather than add a side-channel, ``TimingProfiler`` accepts token
records via ``record_tokens(agent, input_tokens, output_tokens)``
so callers (the orchestrator, tests, the cinematic demo) can
supply counts when they have them. The counter just aggregates.
Future work: the AIClient grows a ``.last_usage`` property that
the orchestrator forwards after each LLM call.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from observability.tracer import ExecutionEvent, ExecutionTracer


# ---------------------------------------------------------------------------
# Distribution container
# ---------------------------------------------------------------------------


@dataclass
class LatencyDistribution:
    """Latency stats for one stage/agent — samples + summaries."""

    label: str
    samples_ms: list[float] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.samples_ms)

    @property
    def total_ms(self) -> float:
        return round(sum(self.samples_ms), 2)

    @property
    def mean_ms(self) -> float:
        return round(statistics.mean(self.samples_ms), 2) if self.samples_ms else 0.0

    @property
    def max_ms(self) -> float:
        return round(max(self.samples_ms), 2) if self.samples_ms else 0.0

    @property
    def min_ms(self) -> float:
        return round(min(self.samples_ms), 2) if self.samples_ms else 0.0

    def percentile(self, p: float) -> float:
        """Return the pth percentile (p in [0.0, 1.0]).

        Uses ``statistics.quantiles`` for n >= 10; falls back to a
        sorted-index probe for smaller samples so the number is
        still meaningful on short demo runs.
        """
        if not self.samples_ms:
            return 0.0
        if p <= 0.0:
            return self.min_ms
        if p >= 1.0:
            return self.max_ms
        if len(self.samples_ms) >= 10:
            # quantiles(n=100) gives percentile boundaries.
            qs = statistics.quantiles(self.samples_ms, n=100, method="inclusive")
            idx = max(0, min(len(qs) - 1, int(p * 100) - 1))
            return round(qs[idx], 2)
        sorted_samples = sorted(self.samples_ms)
        idx = min(len(sorted_samples) - 1, int(p * len(sorted_samples)))
        return round(sorted_samples[idx], 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "count": self.count,
            "total_ms": self.total_ms,
            "mean_ms": self.mean_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "p50_ms": self.percentile(0.5),
            "p95_ms": self.percentile(0.95),
            "p99_ms": self.percentile(0.99),
        }


# ---------------------------------------------------------------------------
# Token usage
# ---------------------------------------------------------------------------


@dataclass
class TokenUsage:
    """Per-agent token counters."""

    agent: str
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "calls": self.calls,
        }


# ---------------------------------------------------------------------------
# Profiler
# ---------------------------------------------------------------------------


# The three brief-named latency buckets we need to surface
# individually (orchestration, verification, retrieval) map onto
# ExecutionEvent kinds. Any event whose kind isn't in this dict
# still contributes to the per-stage + per-agent timing; we just
# don't bucket it into one of these headline labels.
_KIND_TO_BUCKET: dict[str, str] = {
    "deterministic_rule": "orchestration",
    "gemini_step": "orchestration",
    "agent_activation": "orchestration",
    "routing_decision": "orchestration",
    "verification_event": "verification",
    "evidence_retrieval": "retrieval",
    "mcp_interaction": "mcp",
}


@dataclass
class TimingProfiler:
    """Per-stage + per-agent latency + token usage.

    Stateful. One instance per swarm session. Construction is
    zero-arg. ``attach(tracer)`` subscribes to a tracer for
    incremental updates.
    """

    _by_stage: dict[str, LatencyDistribution] = field(
        default_factory=lambda: defaultdict(lambda: LatencyDistribution(label=""))
    )
    _by_agent: dict[str, LatencyDistribution] = field(
        default_factory=lambda: defaultdict(lambda: LatencyDistribution(label=""))
    )
    _by_bucket: dict[str, LatencyDistribution] = field(
        default_factory=lambda: defaultdict(lambda: LatencyDistribution(label=""))
    )
    _tokens: dict[str, TokenUsage] = field(default_factory=dict)
    _failures: int = 0
    _total_events: int = 0

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def attach(self, tracer: "ExecutionTracer") -> None:
        """Subscribe to a tracer — every new event updates the profiler."""
        tracer.on_event(self._on_event)
        # Also backfill with any events the tracer already has.
        for ev in tracer.events:
            self._on_event(ev)

    # ------------------------------------------------------------------
    # Direct API (use without a tracer)
    # ------------------------------------------------------------------

    def record(
        self, *, stage: str, duration_ms: float,
        agent: str = "", bucket: str = "", status: str = "success",
    ) -> None:
        """Record one latency sample. ``stage`` is the primary key."""
        self._record_stage(stage, duration_ms)
        if agent:
            self._record_agent(agent, duration_ms)
        if bucket:
            self._record_bucket(bucket, duration_ms)
        self._total_events += 1
        if status == "error":
            self._failures += 1

    def record_tokens(
        self, *, agent: str, input_tokens: int = 0, output_tokens: int = 0,
    ) -> None:
        """Record one LLM call's token usage."""
        bucket = self._tokens.get(agent)
        if bucket is None:
            bucket = TokenUsage(agent=agent)
            self._tokens[agent] = bucket
        bucket.input_tokens += int(input_tokens)
        bucket.output_tokens += int(output_tokens)
        bucket.calls += 1

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def stage(self, name: str) -> LatencyDistribution:
        """Fetch the distribution for one stage/step name."""
        return self._by_stage.get(name, LatencyDistribution(label=name))

    def agent(self, agent_id: str) -> LatencyDistribution:
        return self._by_agent.get(agent_id, LatencyDistribution(label=agent_id))

    def bucket(self, bucket_name: str) -> LatencyDistribution:
        """Fetch orchestration / verification / retrieval / mcp aggregate."""
        return self._by_bucket.get(bucket_name, LatencyDistribution(label=bucket_name))

    @property
    def failure_rate(self) -> float:
        """Fraction of ingested events marked status='error' [0.0, 1.0]."""
        if self._total_events == 0:
            return 0.0
        return round(self._failures / self._total_events, 4)

    @property
    def total_tokens(self) -> int:
        return sum(t.total_tokens for t in self._tokens.values())

    @property
    def total_llm_calls(self) -> int:
        return sum(t.calls for t in self._tokens.values())

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def latency_report(self) -> dict[str, Any]:
        """Compact dict report of latency buckets + top-N stages."""
        by_bucket = {
            name: dist.to_dict()
            for name, dist in sorted(self._by_bucket.items())
        }
        top_stages = sorted(
            self._by_stage.values(),
            key=lambda d: d.total_ms,
            reverse=True,
        )[:10]
        top_agents = sorted(
            self._by_agent.values(),
            key=lambda d: d.total_ms,
            reverse=True,
        )[:10]
        return {
            "total_events": self._total_events,
            "failure_rate": self.failure_rate,
            "by_bucket": by_bucket,
            "top_stages": [d.to_dict() for d in top_stages if d.count > 0],
            "top_agents": [d.to_dict() for d in top_agents if d.count > 0],
        }

    def token_report(self) -> dict[str, Any]:
        """Compact dict report of token usage per agent."""
        return {
            "total_tokens": self.total_tokens,
            "total_calls": self.total_llm_calls,
            "by_agent": {a: t.to_dict() for a, t in sorted(self._tokens.items())},
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "latency": self.latency_report(),
            "tokens": self.token_report(),
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _on_event(self, ev: "ExecutionEvent") -> None:
        """Tracer subscription callback."""
        self._total_events += 1
        if ev.status == "error":
            self._failures += 1

        duration = max(0.0, float(ev.duration_ms or 0.0))
        self._record_stage(ev.name, duration)

        bucket = _KIND_TO_BUCKET.get(ev.kind.value)
        if bucket:
            self._record_bucket(bucket, duration)

        # Agent attribution — activation events carry an agent_id in
        # payload; mcp events carry 'called_by' in payload; others
        # derive an agent from the step name prefix.
        agent = _derive_agent(ev)
        if agent:
            self._record_agent(agent, duration)

    def _record_stage(self, name: str, duration_ms: float) -> None:
        d = self._by_stage[name]
        if not d.label:
            d.label = name
        d.samples_ms.append(duration_ms)

    def _record_agent(self, agent: str, duration_ms: float) -> None:
        d = self._by_agent[agent]
        if not d.label:
            d.label = agent
        d.samples_ms.append(duration_ms)

    def _record_bucket(self, bucket: str, duration_ms: float) -> None:
        d = self._by_bucket[bucket]
        if not d.label:
            d.label = bucket
        d.samples_ms.append(duration_ms)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_agent(ev: "ExecutionEvent") -> str:
    """Best-effort agent id extraction from an event."""
    payload = ev.payload or {}
    # Activation events have a direct ``agent_id`` field.
    agent = payload.get("agent_id")
    if isinstance(agent, str) and agent:
        return agent
    # MCP events carry called_by in payload if available.
    called = payload.get("called_by")
    if isinstance(called, str) and called:
        return called
    # Step names like 'execute:pharmacogene_cyp2c19' → 'pharmacogene_cyp2c19'
    if ":" in ev.name:
        return ev.name.split(":", 1)[1].strip()
    return ""


__all__ = [
    "TimingProfiler",
    "LatencyDistribution",
    "TokenUsage",
]
