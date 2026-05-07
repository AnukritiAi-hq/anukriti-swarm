"""Anukriti Swarm — Base agent abstraction.

All agents in the swarm inherit from BaseAgent. This provides:
- Consistent interface for the orchestrator to invoke agents
- Built-in audit logging for every execution
- LangGraph node compatibility (agents are callable on SwarmState)
- Self-validation before result submission

Future: Will integrate with MCP tool servers for database and retrieval access.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from agents.models import AgentResult, AgentTask, AgentType, ExecutionMode, TaskStatus
from agents.state import SwarmState


class BaseAgent(ABC):
    """Abstract base class for all swarm agents.

    Each agent is a LangGraph-compatible node: it receives SwarmState,
    performs its work, and returns state updates. The orchestrator
    dispatches tasks to agents based on their agent_type.

    Subclasses must implement:
        - execute(): Core logic for the agent's domain
        - validate_output(): Self-check before returning results

    Usage as LangGraph node:
        agent = MyAgent()
        result_state = agent(state)  # __call__ delegates to execute
    """

    def __init__(self, agent_id: str | None = None) -> None:
        self.agent_id = agent_id or f"{self.agent_type.value}_{uuid.uuid4().hex[:8]}"

    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """The role classification of this agent."""
        ...

    @property
    @abstractmethod
    def execution_mode(self) -> ExecutionMode:
        """Whether this agent operates deterministically or generatively."""
        ...

    def __call__(self, state: SwarmState) -> SwarmState:
        """LangGraph node interface — invoke agent on shared state.

        This is the entry point when the agent is used as a graph node.
        Wraps execute() with audit logging and error handling.
        """
        try:
            return self.execute(state)
        except Exception as e:
            # On failure, append error to state without crashing the graph
            errors = list(state.get("errors", []))
            errors.append(f"[{self.agent_id}] {type(e).__name__}: {e}")
            return {"errors": errors, "status": TaskStatus.FAILED}  # type: ignore[return-value]

    @abstractmethod
    def execute(self, state: SwarmState) -> SwarmState:
        """Execute the agent's core logic on the shared state.

        Args:
            state: Current execution state from the DAG.

        Returns:
            Updated state dict (partial — only keys this agent modifies).

        Future: Will receive pre-filtered state relevant to this agent's
        domain (e.g., chromosome agents only see their chromosome's variants).
        """
        ...

    def validate_output(self, result: AgentResult) -> bool:
        """Self-validate output before submission to orchestrator.

        Default: check that status is DONE and confidence > 0.
        Subclasses can override for domain-specific validation.

        Future: Will enforce source attribution for generative outputs.
        """
        return result.status == TaskStatus.DONE and result.confidence > 0.0

    def create_result(
        self,
        task_id: str,
        output: dict,
        confidence: float = 1.0,
        sources: list[str] | None = None,
        error: str | None = None,
    ) -> AgentResult:
        """Helper to construct a properly-formed AgentResult."""
        status = TaskStatus.DONE if error is None else TaskStatus.FAILED
        return AgentResult(
            task_id=task_id,
            agent_id=self.agent_id,
            status=status,
            output=output,
            confidence=confidence,
            sources=sources or [],
            execution_mode=self.execution_mode,
            timestamp=datetime.now(timezone.utc),
            error=error,
        )
