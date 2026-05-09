"""Anukriti Swarm — interoperable genomic-agent communication layer.

**Scope firewall (strict):**
This package supports interoperability for **genomic intelligence
workflows only**. It is *not* a generic healthcare agent framework,
hospital management system, EHR integration, clinical copilot,
appointment workflow, or health-dashboard platform. The brief
explicitly names these as out-of-scope, and every class here
enforces that boundary.

What this package does
----------------------
Wraps the existing ``communication/`` transport primitives,
``core.verification`` safety engine, ``integrations.mcp``
persistence, and ``core.orchestrator.context`` execution context
into 5 named classes + one shared context + 5 A2A-style workflow
primitives. The composition lets specialist genomic agents
(population / pharmacogene / retrieval / verification / safety /
narrative) collaborate peer-to-peer through:

    - structured message passing      (AgentMessageBus)
    - shared biomedical context       (SharedBiomedicalContext)
    - provenance-aware communication  (ProvenancePropagationLayer)
    - deterministic verification gate (VerificationStatePropagator)

What this package does *not* do
-------------------------------
- Does **not** route clinical-workflow messages (lab orders,
  scheduling, billing, discharge, patient records, prescriptions
  outside the PGx risk-analysis context).
- Does **not** expose a generic agent-to-agent protocol —
  only biomedical_context_type messages shaped by the shared
  context pass through. Unknown context types are rejected.
- Does **not** replace ``communication/`` — this package sits
  on top. Every existing caller keeps working unchanged.

Core workflow preserved
-----------------------
The platform's public-facing contract stays unchanged:

    Drug + Population + Genotype
        → population-aware reasoning
        → pharmacogenomic analysis
        → evidence retrieval
        → deterministic verification
        → explainable risk synthesis

This package makes the *internals* of that workflow interoperable
(agents talk via the bus instead of only via the orchestrator) —
not the workflow itself.

Public surface (lands progressively):

    AgentContextEnvelope          message + verification + confidence
                                  + biomedical_context_type
    AgentMessageBus               context-aware routing
    SharedBiomedicalContext       bundled domain state
    SwarmContextProtocol          agent read/write contract
    ProvenancePropagationLayer    stamps MCP provenance on outbound
    VerificationStatePropagator   safety-gated message delivery

    a2a.delegate_to_specialist    agent-to-agent delegation
    a2a.collaborate               parallel specialist invocation
    a2a.escalate_to_safety        verification-handoff to safety agent
    a2a.verify_handoff            per-claim verification
    a2a.sync_evidence             bi-directional evidence exchange
"""

from __future__ import annotations

from interoperability.shared_context import (
    AgentContextEnvelope,
    BiomedicalContextType,
    ConfidenceLevel,
    VerificationState,
)

# Public API — filled in progressively across the 10 commits.
__all__: list[str] = [
    "AgentContextEnvelope",
    "BiomedicalContextType",
    "VerificationState",
    "ConfidenceLevel",
]
