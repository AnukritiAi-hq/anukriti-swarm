"""Message bus for inter-agent routing and delivery.

Provides in-process message routing with:
- Agent registration and discovery
- Message delivery with status tracking
- Dead letter queue for undeliverable messages
- Message history for audit trail reconstruction

Compatibility:
- Synchronous execution (current)
- Async-ready interface (future: swap to asyncio queues)
- Distributed: serializable messages can be routed over network
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from communication.messages import DeliveryStatus, MessageEnvelope, MessageType


# Handler type: receives a message, optionally returns a reply
MessageHandler = Callable[[MessageEnvelope], MessageEnvelope | None]


class MessageBus:
    """In-process message bus for agent communication.

    Agents register handlers for specific message types. The bus routes
    incoming messages to the appropriate handler and tracks delivery status.

    Future: Will support async dispatch, priority queuing, and
    network-based routing for distributed execution.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, MessageHandler] = {}  # agent_id → handler
        self._type_handlers: dict[MessageType, list[MessageHandler]] = defaultdict(list)
        self._history: list[MessageEnvelope] = []
        self._dead_letters: list[MessageEnvelope] = []

    def register(self, agent_id: str, handler: MessageHandler) -> None:
        """Register an agent's message handler."""
        self._handlers[agent_id] = handler

    def subscribe(self, message_type: MessageType, handler: MessageHandler) -> None:
        """Subscribe a handler to a specific message type (pub/sub pattern)."""
        self._type_handlers[message_type].append(handler)

    def send(self, message: MessageEnvelope) -> MessageEnvelope | None:
        """Send a message and return any synchronous reply.

        Routing:
        1. If target_agent is set → direct delivery to that agent's handler
        2. If target_agent is None → broadcast to type subscribers
        3. If no handler found → dead letter queue
        """
        self._history.append(message)

        # Direct delivery
        if message.target_agent and message.target_agent in self._handlers:
            handler = self._handlers[message.target_agent]
            reply = handler(message)
            self._mark_delivered(message)
            if reply:
                self._history.append(reply)
            return reply

        # Type-based pub/sub
        if message.message_type in self._type_handlers:
            for handler in self._type_handlers[message.message_type]:
                handler(message)
            self._mark_delivered(message)
            return None

        # Undeliverable
        self._dead_letters.append(message)
        return None

    def get_history(self, correlation_id: str | None = None) -> list[MessageEnvelope]:
        """Get message history, optionally filtered by correlation_id."""
        if correlation_id:
            return [m for m in self._history if m.correlation_id == correlation_id]
        return list(self._history)

    @property
    def dead_letters(self) -> list[MessageEnvelope]:
        """Messages that could not be delivered."""
        return list(self._dead_letters)

    def _mark_delivered(self, message: MessageEnvelope) -> None:
        """Track delivery (note: frozen model, so we track separately)."""
        # In production, this would update a delivery status store
        pass
