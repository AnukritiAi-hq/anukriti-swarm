"""A2A-style communication patterns.

Higher-level abstractions over the message bus for common agent
interaction patterns: request/response, delegation, and escalation.

These patterns encapsulate the message creation, sending, and
response handling so agents can communicate with simple method calls.

Patterns:
- delegate_task(): orchestrator assigns work to a specialist
- request_evidence(): any agent requests evidence from retrieval
- escalate(): any agent triggers human review
- broadcast_update(): orchestrator notifies all agents of state change
"""

from __future__ import annotations

from typing import Any

from communication.bus import MessageBus
from communication.context import ExecutionContext
from communication.messages import (
    MessageEnvelope,
    MessageType,
    Priority,
    escalation_payload,
    evidence_request_payload,
    task_delegate_payload,
)


class AgentCommunicator:
    """A2A communication interface for a single agent.

    Each agent gets a communicator instance that provides typed methods
    for common interaction patterns. The communicator handles message
    construction, context propagation, and bus routing.

    Usage:
        comm = AgentCommunicator("orchestrator_01", bus, context)
        reply = comm.delegate_task("population_sas", "frequency_lookup", {"gene": "CYP2D6"})
    """

    def __init__(self, agent_id: str, bus: MessageBus, context: ExecutionContext) -> None:
        self.agent_id = agent_id
        self.bus = bus
        self.context = context

    def delegate_task(
        self,
        target_agent: str,
        task_type: str,
        parameters: dict[str, Any],
        timeout: int = 30,
    ) -> MessageEnvelope | None:
        """Delegate a task to another agent (request/response)."""
        msg = MessageEnvelope(
            source_agent=self.agent_id,
            target_agent=target_agent,
            message_type=MessageType.TASK_DELEGATE,
            payload=task_delegate_payload(
                task_id=f"{task_type}_{self.context.correlation_id[:8]}",
                agent_type=task_type,
                parameters=parameters,
                timeout=timeout,
            ),
            correlation_id=self.context.correlation_id,
            priority=Priority(self.context.priority),
        )
        return self.bus.send(msg)

    def request_evidence(
        self, target_agent: str, gene: str, query: str, top_k: int = 5
    ) -> MessageEnvelope | None:
        """Request evidence from a retrieval agent."""
        msg = MessageEnvelope(
            source_agent=self.agent_id,
            target_agent=target_agent,
            message_type=MessageType.EVIDENCE_REQUEST,
            payload=evidence_request_payload(gene=gene, query=query, top_k=top_k),
            correlation_id=self.context.correlation_id,
        )
        return self.bus.send(msg)

    def escalate(self, reason: str, severity: str = "medium", context: dict[str, Any] | None = None) -> None:
        """Trigger an escalation event for human review."""
        msg = MessageEnvelope(
            source_agent=self.agent_id,
            target_agent=None,  # Broadcast
            message_type=MessageType.ESCALATION,
            payload=escalation_payload(reason=reason, severity=severity, context=context),
            correlation_id=self.context.correlation_id,
            priority=Priority.HIGH,
        )
        self.bus.send(msg)

    def send_result(self, target_agent: str, result: dict[str, Any], reply_to: str | None = None) -> None:
        """Send a task result back to the requesting agent."""
        msg = MessageEnvelope(
            source_agent=self.agent_id,
            target_agent=target_agent,
            message_type=MessageType.TASK_RESULT,
            payload=result,
            correlation_id=self.context.correlation_id,
            reply_to=reply_to,
        )
        self.bus.send(msg)

    def broadcast_update(self, action: str, details: dict[str, Any] | None = None) -> None:
        """Broadcast an orchestration update to all listeners."""
        msg = MessageEnvelope(
            source_agent=self.agent_id,
            target_agent=None,
            message_type=MessageType.ORCHESTRATION_UPDATE,
            payload={"action": action, "details": details or {}},
            correlation_id=self.context.correlation_id,
        )
        self.bus.send(msg)
