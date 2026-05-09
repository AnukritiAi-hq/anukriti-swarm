"""Interoperability — A2A (agent-to-agent) workflow subpackage.

Hosts the 5 brief-named collaboration primitives (commit 8) —
pure functions over ``AgentMessageBus`` + ``SharedBiomedicalContext``:

    delegate_to_specialist    orchestrator-to-specialist dispatch
    collaborate               parallel specialist invocation
    escalate_to_safety        verification-failure handoff
    verify_handoff            per-claim verification exchange
    sync_evidence             bi-directional evidence propagation

These are **genomic-scoped**: they refuse to delegate to agents that
aren't registered with a genomic role, and every message they produce
carries a biomedical_context_type header.
"""

from __future__ import annotations

from interoperability.a2a.workflows import (
    CollaborationResult,
    DelegationResult,
    collaborate,
    delegate_to_specialist,
    escalate_to_safety,
    sync_evidence,
    verify_handoff,
)

__all__ = [
    "DelegationResult",
    "CollaborationResult",
    "delegate_to_specialist",
    "collaborate",
    "escalate_to_safety",
    "verify_handoff",
    "sync_evidence",
]
