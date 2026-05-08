"""``AgentRouter`` — maps planned actions onto concrete specialist agents.

The planner emits abstract substep names (``"pharmacogene_analysis"``,
``"population_analysis"``, …). The router turns each of those into a
concrete agent ID (``"pharmacogene_cyp2c19"``, ``"population_sas"``, …)
using the existing ``AgentRegistry``.

The router is **deterministic**. Gemini's advisory routing from the
planner is informational only — the actual selection is rule-based
so routing is reproducible, auditable, and cannot drift between runs.

Responsibilities:

1. For each ``PlannedStep``, resolve the set of concrete agents that
   should handle it, given the context (gene / drug / population).
2. Record an ``ActivationLog`` on the trace with the reason.
3. Update ``ctx.active_agents``.
4. Detect "no agent available" situations and surface them as
   routing errors (the coordinator will turn those into escalations).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from agents.profiles.identity import AgentDomain, AgentProfile
from agents.registry.registry import AgentRegistry
from core.orchestrator.context import OrchestrationPhase, SwarmExecutionContext
from core.orchestrator.planner import PlannedStep


# ---------------------------------------------------------------------------
# Action → domain mapping
# ---------------------------------------------------------------------------
#
# Each planner action corresponds to one or more agent domains. The router
# uses this as the *starting* filter before narrowing by gene / population.
# Actions that don't map to a specialist agent (comparative_analysis,
# narrative_synthesis) are handled directly by the coordinator.

_ACTION_DOMAINS: dict[str, tuple[AgentDomain, ...]] = {
    "population_analysis": (AgentDomain.POPULATION_GENOMICS,),
    "pharmacogene_analysis": (AgentDomain.PHARMACOGENOMICS,),
    "evidence_retrieval": (AgentDomain.EVIDENCE_RETRIEVAL,),
    "verification": (AgentDomain.VERIFICATION,),
    # Handled by the coordinator itself — no registry lookup:
    "comparative_analysis": (),
    "narrative_synthesis": (),
}


@dataclass
class RouteDecision:
    """Per-step routing outcome."""

    step: PlannedStep
    agents: list[AgentProfile] = field(default_factory=list)
    reason: str = ""
    skipped: bool = False  # True when the action is handled by the coordinator


@dataclass
class RoutingResult:
    """Aggregate result of routing a whole plan."""

    decisions: list[RouteDecision]
    errors: list[str]
    duration_ms: float

    @property
    def activated_agent_ids(self) -> list[str]:
        """De-duplicated ordered list of agent IDs touched by routing."""
        seen: set[str] = set()
        ordered: list[str] = []
        for d in self.decisions:
            for a in d.agents:
                if a.agent_id not in seen:
                    seen.add(a.agent_id)
                    ordered.append(a.agent_id)
        return ordered


class AgentRouter:
    """Resolve planned substeps to concrete specialist agents."""

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        if registry is None:
            registry = AgentRegistry()
            registry.register_all()
        self.registry = registry

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def route(
        self, ctx: SwarmExecutionContext, steps: list[PlannedStep]
    ) -> RoutingResult:
        """Resolve an entire plan.

        Side effects:
          - adds one ActivationLog per selected agent to ctx.orchestration_trace
          - calls ctx.activate_agent for each selected agent
          - records a single StepMetric ("route") summarizing the pass
          - advances phase to ROUTING -> EXECUTING on exit
        """
        ctx.mark_phase(OrchestrationPhase.ROUTING)
        trace = ctx.ensure_trace()
        t0 = time.perf_counter()

        decisions: list[RouteDecision] = []
        errors: list[str] = []

        for step in steps:
            decision = self._route_step(ctx, step)
            decisions.append(decision)

            if decision.skipped:
                continue

            if not decision.agents:
                err = (
                    f"routing: no agent matched action='{step.action}' "
                    f"for gene='{ctx.gene}' population='{ctx.population}'"
                )
                errors.append(err)
                ctx.record_error(err)
                continue

            for agent in decision.agents:
                trace.record_activation(
                    agent_id=agent.agent_id,
                    role=agent.domain.value,
                    reason=decision.reason,
                )
                ctx.activate_agent(agent.agent_id)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        # For each concrete agent surfaced, emit a lightweight
        # "route:<agent_id>" step so activations are visible in step-level
        # timeline views as well as in the activations list.
        for agent_id in _unique_ordered(
            aid for d in decisions for a in d.agents for aid in [a.agent_id]
        ):
            trace.record_step(
                f"route:{agent_id}",
                origin="deterministic",
                duration_ms=0.0,
                status="success",
            )

        trace.record_step(
            "route",
            origin="deterministic",
            duration_ms=elapsed_ms,
            status="warning" if errors else "success",
            decisions=[
                {
                    "action": d.step.action,
                    "agents": [a.agent_id for a in d.agents],
                    "skipped": d.skipped,
                }
                for d in decisions
            ],
            errors=errors,
        )

        ctx.mark_phase(OrchestrationPhase.EXECUTING)
        return RoutingResult(decisions=decisions, errors=errors, duration_ms=elapsed_ms)

    # ------------------------------------------------------------------
    # Per-step routing
    # ------------------------------------------------------------------

    def _route_step(
        self, ctx: SwarmExecutionContext, step: PlannedStep
    ) -> RouteDecision:
        """Resolve a single planned step to agents (or mark it skipped)."""
        domains = _ACTION_DOMAINS.get(step.action, ())
        if not domains:
            # Coordinator-handled action (comparative_analysis,
            # narrative_synthesis). No registry involvement.
            return RouteDecision(
                step=step,
                skipped=True,
                reason=f"'{step.action}' is handled by the coordinator",
            )

        # Population_analysis fans out across ctx.populations when present.
        if step.action == "population_analysis" and ctx.populations:
            agents: list[AgentProfile] = []
            reasons: list[str] = []
            for pop in ctx.populations:
                picked = self._pick_by_domain(
                    domains, gene=ctx.gene, population=pop, drug=ctx.drug
                )
                agents.extend(picked)
                reasons.append(f"population={pop}")
            return RouteDecision(
                step=step,
                agents=_dedup(agents),
                reason="; ".join(reasons),
            )

        agents = self._pick_by_domain(
            domains, gene=ctx.gene, population=ctx.population, drug=ctx.drug
        )
        why_parts: list[str] = []
        if ctx.gene and step.action == "pharmacogene_analysis":
            why_parts.append(f"gene={ctx.gene}")
        if ctx.population and step.action == "population_analysis":
            why_parts.append(f"population={ctx.population}")
        if not why_parts:
            why_parts.append(f"domain={domains[0].value}")
        return RouteDecision(
            step=step,
            agents=agents,
            reason=", ".join(why_parts),
        )

    def _pick_by_domain(
        self,
        domains: tuple[AgentDomain, ...],
        *,
        gene: str = "",
        population: str = "",
        drug: str = "",
    ) -> list[AgentProfile]:
        """Find agents matching any of the domains and the query filters.

        If a gene / population / drug filter is specified, it is used
        to narrow — but only within the matching domain(s). Query fields
        that don't apply to the domain (e.g. ``gene`` for a population
        agent) are ignored by ``AgentProfile.matches_query`` because
        ``AgentProfile`` treats an empty ``supported_genes`` as "any".
        """
        candidates: list[AgentProfile] = []
        for domain in domains:
            candidates.extend(self.registry.find_by_domain(domain))

        filtered = [
            c
            for c in candidates
            if c.matches_query(
                gene=gene or None, drug=drug or None, population=population or None
            )
        ]
        # Priority-ordered (lower = more specific)
        return sorted(filtered, key=lambda a: a.priority)


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------


def _dedup(agents: list[AgentProfile]) -> list[AgentProfile]:
    """Order-preserving dedup by agent_id."""
    seen: set[str] = set()
    out: list[AgentProfile] = []
    for a in agents:
        if a.agent_id not in seen:
            seen.add(a.agent_id)
            out.append(a)
    return out


def _unique_ordered(items):
    seen: set = set()
    out: list = []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


__all__ = ["AgentRouter", "RouteDecision", "RoutingResult"]
