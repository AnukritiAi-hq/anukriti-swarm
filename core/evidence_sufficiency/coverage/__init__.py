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
    EvidenceCoverageAnalyzer    pure function over retrieval + MCP
                                outputs → ClaimCoverageAnalysis
    ProvenanceCoverageTracker   reads MCP provenance chain; flags
                                missing rule / agent / source
                                attribution links

Every class here is deterministic and free of LLM calls.
"""

from __future__ import annotations

__all__: list[str] = []
