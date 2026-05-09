"""Interoperability — shared context subpackage.

Hosts the canonical biomedical context types specialist agents use
to collaborate:

    AgentContextEnvelope     (commit 2)  message + verification +
                                          confidence + biomedical
                                          context type
    SharedBiomedicalContext  (commit 4)  bundled domain state —
                                          ancestry / population /
                                          genotype / frequencies /
                                          phenotype / drug / evidence
                                          graph / verification graph
    SwarmContextProtocol     (commit 5)  read/write contract with
                                          genomic-scope enforcement
"""

from __future__ import annotations

from interoperability.shared_context.envelope import (
    AgentContextEnvelope,
    BiomedicalContextType,
    ConfidenceLevel,
    VerificationState,
)

__all__: list[str] = [
    "AgentContextEnvelope",
    "BiomedicalContextType",
    "VerificationState",
    "ConfidenceLevel",
]
