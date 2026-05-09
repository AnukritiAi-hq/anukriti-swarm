"""Evidence Sufficiency — ``coverage/`` subpackage.

Facet-level and provenance-level coverage analyzers. Where the
existing ``GroundingReport.coverage`` is *source* coverage
(did the cited ids resolve?), this subpackage measures *semantic
facet* coverage: for a given pharmacogenomic tuple (drug, gene,
population, genotype), do we have at least one piece of evidence
for each of the six closed facets the platform requires for safe
synthesis?

Public surface:

    ClaimCoverageAnalysis       frozen per-run record enumerating
                                which of the six facets are
                                satisfied, missing, or uncertain
                                (commit 2)
    ClaimEvidenceFacet          closed enum — 6 facets (commit 2)
    FacetCoverageState          closed enum — covered / missing /
                                uncertain (commit 2)
    ALL_FACETS                  canonical iteration order (commit 2)
    EvidenceCoverageAnalyzer    deterministic function over
                                run + retrieval docs →
                                ClaimCoverageAnalysis (commit 3)
    ProvenanceCoverageTracker   deterministic audit over
                                ProvenanceRecord-shaped items →
                                ProvenanceCoverageReport (commit 3)
    ProvenanceDimension         closed enum — rule_id /
                                agent_attribution /
                                chain_completeness /
                                evidence_resolvability (commit 3)
    DimensionState              closed enum — covered / missing
                                (commit 3)
    ALL_DIMENSIONS              canonical iteration order (commit 3)
    ProvenanceCoverageReport    frozen attribution-dimension report
                                (commit 3)

Every class here is deterministic and free of LLM calls.
"""

from __future__ import annotations

from core.evidence_sufficiency.coverage.analyzer import EvidenceCoverageAnalyzer
from core.evidence_sufficiency.coverage.claim_coverage import (
    ALL_FACETS,
    ClaimCoverageAnalysis,
    ClaimEvidenceFacet,
    FacetCoverageState,
)
from core.evidence_sufficiency.coverage.provenance_tracker import (
    ALL_DIMENSIONS,
    DimensionState,
    ProvenanceCoverageReport,
    ProvenanceCoverageTracker,
    ProvenanceDimension,
)

__all__ = [
    # claim coverage
    "ALL_FACETS",
    "ClaimCoverageAnalysis",
    "ClaimEvidenceFacet",
    "FacetCoverageState",
    # analyzer
    "EvidenceCoverageAnalyzer",
    # provenance tracking
    "ALL_DIMENSIONS",
    "DimensionState",
    "ProvenanceCoverageReport",
    "ProvenanceCoverageTracker",
    "ProvenanceDimension",
]
