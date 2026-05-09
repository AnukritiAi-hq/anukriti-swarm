"""Evidence Sufficiency — ``conflict/`` subpackage.

Hosts ``ConflictDetectionAgent`` — a deterministic checker that looks
across the retrieved evidence set for contradictory signals before
synthesis runs.

The agent is *not* a general claim-reasoner. It detects exactly three
pharmacogenomic conflict classes:

    1. Phenotype disagreement   two sources predict different
                                metabolizer phenotypes for the same
                                diplotype in the same population
    2. Recommendation clash     two guideline sources recommend
                                incompatible actions for the same
                                drug-gene-phenotype tuple
    3. Population divergence    a claim's cited sources report
                                materially different allele
                                frequencies in the same ancestry
                                group (beyond declared tolerance)

If a conflict is detected, downstream synthesis is blocked via the
``CONFLICT_FREE`` facet on ``ClaimCoverageAnalysis`` being downgraded
to MISSING (hard) or UNCERTAIN (soft). The escalation workflow then
picks up the facet state — same pattern as the existing
``core.verification.EscalationWorkflow``.

Public surface (all added in commit 4):

    ConflictKind              closed enum (3 classes)
    ConflictSeverity          closed enum (HARD / SOFT)
    RecommendationAction      closed enum (use / avoid /
                              consider_alt / contraindicated /
                              unknown) used by the recommendation
                              clash detector
    ConflictFinding           frozen audit record
    ConflictDetectionAgent    stateless detector
"""

from __future__ import annotations

from core.evidence_sufficiency.conflict.agent import (
    ConflictDetectionAgent,
    ConflictFinding,
    ConflictKind,
    ConflictSeverity,
    RecommendationAction,
    classify_action,
)

__all__ = [
    "ConflictDetectionAgent",
    "ConflictFinding",
    "ConflictKind",
    "ConflictSeverity",
    "RecommendationAction",
    "classify_action",
]
