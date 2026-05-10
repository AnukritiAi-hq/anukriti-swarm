"""``EvidenceVerificationResult`` — 5-state set-level verifier outcome.

Phase 4, commit 12 of the Evidence Sufficiency Layer brief.

Defines the shape and closed-enum outcomes of a *set-level* (vs
*claim-level*) evidence judgement. Where
``core.verification.BiomedicalClaimValidator`` emits one
``VerificationTrace`` per claim, this verifier emits **one
``EvidenceVerificationResult`` per run** over the whole evidence
bundle — that is the SURE-RAG move: judge the entire set jointly.

The five outcomes (closed set, extending is a code change)
-----------------------------------------------------------

    SUPPORTED       the evidence set *jointly* supports the core
                    biomedical conclusion for the run's
                    pharmacogenomic tuple. Coverage is complete,
                    relation strength is strong on the driving
                    facets, no conflict, and (if a KG path bundle
                    is supplied) at least one path leads from the
                    allele / phenotype to the drug.

    REFUTED         the evidence set *jointly* contradicts the
                    conclusion — typically because a HARD conflict
                    inverts a core recommendation (e.g. one source
                    says AVOID, another says USE for the same
                    drug/gene/phenotype). Distinct from
                    CONFLICTING: REFUTED means we can name the
                    refuting signal; CONFLICTING means we cannot
                    pick a side.

    INSUFFICIENT    required facets are missing and retrieval has
                    not recovered them. The sufficiency layer
                    would emit BLOCK or REQUEST_MORE; the verifier
                    labels the evidence set itself.

    CONFLICTING     two sources disagree in a way that cannot be
                    resolved from the current bundle. (HARD
                    conflict without a clean invertor.)

    UNCERTAIN       the set is sparse or ancestry-underrepresented;
                    evidence quantity is low or the driving facets
                    are in UNCERTAIN state. The verifier cannot
                    commit to supported/refuted.

Rationale for the split between INSUFFICIENT and UNCERTAIN
----------------------------------------------------------

INSUFFICIENT is an *addressable* shortfall — retrieval could
close the gap. UNCERTAIN is an *epistemic* shortfall — even with
more retrieval the answer might stay ambiguous (e.g. an allele
that is genuinely rare in the target population). The
downstream orchestrator routes these differently: INSUFFICIENT
-> fetch more; UNCERTAIN -> caveat or human review.

Frozen record
-------------

Carries the outcome, a rule-id that names which rule fired (for
audit — same convention as the SufficiencyDecisionEngine's
rationale), and *views* into the already-computed inputs the
verifier read. No inputs are re-interpreted here; the verifier
in commit 13 applies a deterministic rule table on top.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.evidence_sufficiency.conflict.agent import ConflictFinding
    from core.evidence_sufficiency.coverage.claim_coverage import (
        ClaimCoverageAnalysis,
    )

# ---------------------------------------------------------------------------
# Closed-enum outcome
# ---------------------------------------------------------------------------


class EvidenceVerdict(str, Enum):
    """The five allowed set-level verdicts."""

    SUPPORTED = "supported"
    REFUTED = "refuted"
    INSUFFICIENT = "insufficient"
    CONFLICTING = "conflicting"
    UNCERTAIN = "uncertain"


# ---------------------------------------------------------------------------
# Frozen record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceVerificationResult:
    """Frozen per-run verdict from the set-level verifier.

    Fields
    ------
    verdict               closed EvidenceVerdict
    rule_id               which rule fired (V1 .. V10 — see commit
                          13 for the rule table)
    rationale             human-readable explanation naming the
                          drivers (missing facets, conflict
                          severity, path coverage)
    coverage              ClaimCoverageAnalysis the verifier read
    findings              tuple of ConflictFindings
    pathway_complete      True iff the KG path bundle (when given)
                          includes at least one ≥ 1-hop path from
                          the driving allele/phenotype to the drug
    pathway_count         number of paths observed; 0 when no KG
                          bundle is supplied (does not itself
                          cause a demotion — see the rule table)
    evidence_refs         flat tuple of source ids the verdict is
                          built over (coverage + path bundle union)
    correlation_id        propagated for MCP linkage
    created_at            ISO timestamp
    """

    verdict: EvidenceVerdict
    rule_id: str
    rationale: str
    coverage: ClaimCoverageAnalysis
    findings: tuple[ConflictFinding, ...]
    pathway_complete: bool
    pathway_count: int
    evidence_refs: tuple[str, ...]
    correlation_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def allows_synthesis(self) -> bool:
        """True iff downstream synthesis may run on this verdict.

        SUPPORTED -> yes.
        UNCERTAIN / INSUFFICIENT / CONFLICTING / REFUTED -> no.
        """

        return self.verdict is EvidenceVerdict.SUPPORTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "rule_id": self.rule_id,
            "rationale": self.rationale,
            "allows_synthesis": self.allows_synthesis,
            "correlation_id": self.correlation_id,
            "pathway_complete": self.pathway_complete,
            "pathway_count": self.pathway_count,
            "evidence_refs": list(self.evidence_refs),
            "coverage": self.coverage.to_dict(),
            "findings": [f.to_dict() for f in self.findings],
            "created_at": self.created_at.isoformat(),
        }


__all__ = [
    "EvidenceVerdict",
    "EvidenceVerificationResult",
]
