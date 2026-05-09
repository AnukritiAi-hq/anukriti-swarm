"""Unified Swarm Runtime — genomic intelligence mission control.

This package adds the *unified execution lifecycle* on top of the
existing swarm modules. It is NOT a new orchestrator; it is a thin
sequencer that composes what the swarm already ships:

    agents/orchestrator/gemini_orchestrator.py   orchestration
    core/orchestrator/                           routing + coordination
    retrieval/                                   multi-strategy retrieval
    knowledge_graph/                             pharmacogenomic KG
    core/evidence_sufficiency/                   governance / sufficiency
    core/verification/                           deterministic safety
    integrations/mcp/                            provenance persistence
    interoperability/                            agent message bus
    observability/                               execution tracing
    narrative/                                   generative synthesis

into a single callable with a single report output, and emits
orchestration events as the lifecycle progresses so the FastAPI
backend (session #7 phase 3) can stream them over WebSocket to
the live frontend (phase 4).

Scope firewall (read before extending)
--------------------------------------
The runtime accepts **only** the pharmacogenomic tuple
``(drug, gene, population, genotype)`` as input. It produces
**only** a ``UnifiedExecutionReport`` that aggregates the existing
modules' outputs. It does **not**:

    • persist state between runs (MCP already does that)
    • authenticate or authorize users (out of scope)
    • run multiple queries in parallel from a single context
      (one context per run; FastAPI handles concurrency by
      instantiating one runtime per request)
    • expose anything beyond the closed-enum input boundary

Populated through session #7:

    context        UnifiedExecutionContext — mutable per-run state
                   container (phase 1, commit 1)
    report         UnifiedExecutionReport — frozen final record
                   (phase 1, commit 2)
    runtime        SwarmRuntime lifecycle (phase 2)
    events         RuntimeEvent + EventStream (phase 2)
"""

from __future__ import annotations

from core.runtime.context import UnifiedExecutionContext
from core.runtime.events import (
    EventStream,
    InMemoryEventStream,
    RuntimeEvent,
    RuntimeEventKind,
)
from core.runtime.report import UnifiedExecutionReport
from core.runtime.runtime import SwarmRuntime

__all__ = [
    "UnifiedExecutionContext",
    "UnifiedExecutionReport",
    "EventStream",
    "InMemoryEventStream",
    "RuntimeEvent",
    "RuntimeEventKind",
    "SwarmRuntime",
]
