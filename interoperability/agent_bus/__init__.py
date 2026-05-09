"""Interoperability — agent bus subpackage.

Hosts ``AgentMessageBus`` — the context-aware message router built
on top of ``communication.MessageBus``. Kept as a subpackage so
future bus variants (distributed, async-first) can land here
without polluting the top-level interoperability namespace.
"""

from __future__ import annotations

from interoperability.agent_bus.bus import (
    AgentHandler,
    AgentMessageBus,
    BusObserver,
)

__all__ = [
    "AgentMessageBus",
    "AgentHandler",
    "BusObserver",
]
