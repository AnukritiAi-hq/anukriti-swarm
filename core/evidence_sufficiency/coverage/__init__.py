"""Evidence Sufficiency — ``coverage/`` subpackage.

Facet-level and provenance-level coverage analyzers. Where the
existing ``GroundingReport.coverage`` is *source* coverage
(did the cited ids resolve?), this subpackage measures *semantic
facet* coverage: for a given pharmacogenomic tuple (drug, gene,
population, genotype), do we have at least one piece of evidence
for each of the six closed facets the platform requires for safe
synthesis?

Public surface (populated incrementally through phase 1):

    ClaimCoverageAnalysis       frozen per-run record enumerating
                                which of the six facets are
                                satisfied, missing, or uncertain
                                (commit 2)
    ClaimEvidenceFacet          closed enum — 6 facets, extending
                                it is a code change (commit 2)
    FacetCoverageState          closed enum — covered / missing /
                                uncertain (commit 2)
    ALL_FACETS                  canonical iteration order (commit 2)
    EvidenceCoverageAnalyzer    pure function over retrieval + MCP
                                outputs → ClaimCoverageAnalysis
                                (commit 3)
    ProvenanceCoverageTracker   reads MCP provenance chain; flags
                                missing rule / agent / source
                                attribution links (commit 3)

Every class here is deterministic and free of LLM calls.
"""

from __future__ import annotations

from core.evidence_sufficiency.coverage.claim_coverage import (
    ALL_FACETS,
    ClaimCoverageAnalysis,
    ClaimEvidenceFacet,
    FacetCoverageState,
)

__all__ = [
    "ALL_FACETS",
    "ClaimCoverageAnalysis",
    "ClaimEvidenceFacet",
    "FacetCoverageState",
]
