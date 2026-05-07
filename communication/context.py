"""Execution context propagation.

Carries contextual metadata through the agent execution chain:
- Correlation ID for trace linking
- Parent agent chain for provenance
- Execution constraints (timeout, priority)
- Population and drug context for domain routing

Context is propagated automatically when agents delegate tasks,
ensuring full traceability without manual plumbing.

Compatibility:
- MCP: context maps to MCP server environment variables
- Distributed: serializable for cross-process propagation
- OpenTelemetry: trace_id/span_id compatible
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ExecutionContext:
    """Propagated context for an execution chain.

    Created by the orchestrator at pipeline start and passed through
    every agent invocation. Agents can fork context for parallel branches.
    """

    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_agents: list[str] = field(default_factory=list)
    current_agent: str = ""
    stage: str = "unknown"

    # Domain context
    population: str | None = None
    drug_context: list[str] = field(default_factory=list)
    target_genes: list[str] = field(default_factory=list)

    # Constraints
    timeout_seconds: int = 60
    priority: int = 5
    max_depth: int = 10  # Prevent infinite delegation chains

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def depth(self) -> int:
        """Current delegation depth."""
        return len(self.parent_agents)

    def child(self, agent_id: str, stage: str) -> "ExecutionContext":
        """Create a child context for delegation to another agent."""
        return ExecutionContext(
            correlation_id=self.correlation_id,
            trace_id=self.trace_id,
            parent_agents=[*self.parent_agents, self.current_agent] if self.current_agent else list(self.parent_agents),
            current_agent=agent_id,
            stage=stage,
            population=self.population,
            drug_context=list(self.drug_context),
            target_genes=list(self.target_genes),
            timeout_seconds=self.timeout_seconds,
            priority=self.priority,
            max_depth=self.max_depth,
        )

    def can_delegate(self) -> bool:
        """Check if further delegation is allowed (depth limit)."""
        return self.depth < self.max_depth
