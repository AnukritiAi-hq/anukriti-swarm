"""Anukriti Swarm — deterministic verification + biomedical safety engine.

Layered above the verification primitives in the top-level
``verification/`` package (checks, confidence math, TAO escalation).
This package adds the **domain-level** pieces the safety brief requires:

- ``VerificationScore``      5-tier scoring (grounded / partial / unverified
                              / conflicting / unsafe) with a classifier
                              that maps check results onto the tier.
- ``VerificationTrace``      canonical per-claim audit record;
                              serializable for MCP persistence.
- ``BiomedicalClaimValidator`` enforces claim → evidence + rule +
                              source + outcome mapping.
- ``EvidenceGroundingEngine`` grounds each claim against the MCP
                              evidence cache.
- ``SafetyConstraintEngine``  deterministic phenotype / CPIC / allele
                              rule checks plus the block-on-unsafe gate.
- ``ProvenanceValidator``    walks the MCP provenance chain and
                              verifies every claim has a complete
                              claim→rule→evidence ancestry.
- ``EscalationWorkflow``     concrete actions the orchestrator can
                              take when verification fails (reroute,
                              request evidence, downgrade confidence,
                              block output).

Design principles:

1. **Deterministic-first.** Every rule is a pure function of inputs;
   no LLM calls, no non-reproducibility.
2. **Composable.** Each engine is independently usable. The
   ``VerificationAgent`` in ``agents.verification`` composes them.
3. **Auditable.** Every decision produces a ``VerificationTrace``
   with the claim, validator name, evidence refs, verdict,
   confidence, and escalation events — directly persistable to MCP.
4. **Non-destructive to existing code.** The existing
   ``verification/`` primitives stay unchanged. This package sits
   on top and calls into them.
"""

from __future__ import annotations

from core.verification.scoring import (
    VerificationScore,
    VerificationTier,
    classify_score,
    worse_of,
)
from core.verification.trace import (
    EscalationEvent,
    TraceState,
    VerificationTrace,
    make_trace,
)

__all__ = [
    "VerificationScore",
    "VerificationTier",
    "classify_score",
    "worse_of",
    "VerificationTrace",
    "EscalationEvent",
    "TraceState",
    "make_trace",
]
