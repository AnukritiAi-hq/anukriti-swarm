"""Interoperability — MCP protocol subpackage.

Hosts the two propagation layers (commits 6 + 7) that lift the
existing ``integrations.mcp`` + ``core.verification`` primitives
into message-level guarantees:

    ProvenancePropagationLayer    stamps MCP provenance refs on every
                                  outbound ``AgentContextEnvelope``
    VerificationStatePropagator   wraps the safety engine's
                                  ``VerificationOutcome`` into
                                  envelope-level gate decisions

Separate subpackage so the MCP-facing concerns stay visibly distinct
from the core bus + context primitives.
"""

from __future__ import annotations

__all__: list[str] = []
