"""Evidence Sufficiency — ``verifier/`` subpackage.

Hosts ``SetLevelEvidenceVerifier`` (SURE-RAG-inspired) and its result
type ``EvidenceVerificationResult``.

Where ``core.verification.BiomedicalClaimValidator`` operates on one
claim at a time, the set-level verifier reasons over the *whole
evidence bundle* for a run and emits exactly one of five outcomes:

    SUPPORTED       evidence set jointly supports the claim
    REFUTED         evidence set jointly contradicts the claim
    INSUFFICIENT    not enough of the six facets are covered
    CONFLICTING     evidence set is self-contradictory
    UNCERTAIN       evidence is sparse or ancestry-underrepresented

This is a *compositional* verifier — it does not re-open documents or
re-run rules; it reads coverage + conflict + uncertainty outputs that
the preceding analyzers already computed.
"""

from __future__ import annotations

__all__: list[str] = []
