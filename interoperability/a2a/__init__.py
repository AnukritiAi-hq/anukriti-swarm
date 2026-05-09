"""Interoperability — A2A (agent-to-agent) workflow subpackage.

Hosts 5 brief-named collaboration primitives (commit 8) — pure
functions over ``AgentMessageBus`` + ``SharedBiomedicalContext``:

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

__all__: list[str] = []
