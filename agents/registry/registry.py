"""Agent registration and capability discovery.

The registry is the swarm's "phone book" — it knows which agents
exist, what they can do, and how to route queries to them.

Supports:
- Registration of agent profiles
- Query-based agent discovery (gene, drug, population)
- Domain-based filtering
- Capability search
- Priority-ordered routing
"""

from __future__ import annotations

from agents.profiles.catalog import ALL_PROFILES
from agents.profiles.identity import AgentDomain, AgentProfile


class AgentRegistry:
    """Central registry for swarm agent discovery and routing.

    The orchestrator uses this to find the right specialist for each
    sub-task in the execution pipeline.
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentProfile] = {}

    def register(self, profile: AgentProfile) -> None:
        """Register an agent profile."""
        self._agents[profile.agent_id] = profile

    def register_all(self, profiles: list[AgentProfile] | None = None) -> None:
        """Register all profiles from catalog."""
        for p in (profiles or ALL_PROFILES):
            self.register(p)

    def get(self, agent_id: str) -> AgentProfile | None:
        """Get a specific agent profile by ID."""
        return self._agents.get(agent_id)

    def find_by_domain(self, domain: AgentDomain) -> list[AgentProfile]:
        """Find all agents in a specific domain."""
        return sorted(
            [a for a in self._agents.values() if a.domain == domain],
            key=lambda a: a.priority,
        )

    def find_for_query(self, gene: str | None = None, drug: str | None = None, population: str | None = None) -> list[AgentProfile]:
        """Find agents that can handle a specific query, ordered by priority."""
        matches = [a for a in self._agents.values() if a.matches_query(gene, drug, population)]
        return sorted(matches, key=lambda a: a.priority)

    def find_by_capability(self, capability: str) -> list[AgentProfile]:
        """Find agents with a specific capability."""
        return [a for a in self._agents.values() if capability in a.capabilities]

    def find_by_tag(self, tag: str) -> list[AgentProfile]:
        """Find agents with a specific tag."""
        return [a for a in self._agents.values() if tag in a.tags]

    @property
    def all_agents(self) -> list[AgentProfile]:
        """All registered agents, ordered by priority."""
        return sorted(self._agents.values(), key=lambda a: a.priority)

    @property
    def count(self) -> int:
        return len(self._agents)

    def federation_summary(self) -> str:
        """Render the swarm federation as a structured summary."""
        lines = [
            f"Anukriti Swarm Federation — {self.count} agents registered",
            "",
        ]
        by_domain: dict[str, list[AgentProfile]] = {}
        for a in self._agents.values():
            by_domain.setdefault(a.domain.value, []).append(a)

        for domain, agents in sorted(by_domain.items()):
            lines.append(f"  [{domain}]")
            for a in sorted(agents, key=lambda x: x.priority):
                mode = a.reasoning_mode.value[0].upper()
                lines.append(f"    {mode} {a.name:<35} ({a.agent_id})")
            lines.append("")

        return "\n".join(lines)
