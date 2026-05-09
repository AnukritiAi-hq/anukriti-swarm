"""Evidence Sufficiency Layer — **governance, not retrieval**.

This package adds an *epistemic sufficiency* checkpoint on top of the
existing verification + retrieval stacks. It answers one question
between retrieval and synthesis:

    "Do we have enough of the right kinds of biomedical evidence
     to safely generate a pharmacogenomic conclusion for this
     (drug, gene, population, genotype) tuple — right now?"

It is **deterministic** by design (no LLM judgement of sufficiency
itself) and composes four existing deterministic stacks:

    retrieval.evidence           → what documents came back
    core.verification.grounding  → do the cited sources resolve
    core.verification.safety     → do the rules still fire
    integrations.mcp.evidence    → is the MCP cache populated

On the output side it emits a single ``SufficiencyReport`` whose
``decision`` the orchestrator honours *before* any generative
narrative runs.

Scope firewall (read before extending)
--------------------------------------
This layer is **not**:

    • a generic RAG chatbot — inputs are restricted to the
      pharmacogenomic tuple (drug, gene, population, genotype)
    • a document search engine — it wraps the existing
      ``retrieval/`` package, never replaces it
    • a general biomedical assistant — every public type keys on
      pharmacogenomic entities (allele / phenotype / CPIC /
      population); unrelated "medical evidence" is rejected at
      the type boundary by closed enums
    • a GraphRAG framework — the graph (phase 3) carries only
      10 brief-named node kinds; schema is closed
    • an LLM-as-judge — sufficiency is computed from evidence
      *counts* and *facet coverage*, not from a model's opinion
      about the evidence

Public surface (phase 1, commit 5)
----------------------------------

Coverage (``core/evidence_sufficiency/coverage/``):
    ClaimCoverageAnalysis       frozen 6-facet record
    ClaimEvidenceFacet          closed 6-value enum
    FacetCoverageState          closed 3-value enum
    ALL_FACETS                  canonical iteration order
    EvidenceCoverageAnalyzer    deterministic 6-facet producer
    ProvenanceCoverageTracker   deterministic 4-dim auditor
    ProvenanceDimension         closed 4-value enum
    DimensionState              closed 2-value enum
    ALL_DIMENSIONS              canonical iteration order
    ProvenanceCoverageReport    frozen 4-dim report

Conflict (``core/evidence_sufficiency/conflict/``):
    ConflictDetectionAgent      deterministic 3-class detector
    ConflictKind                closed 3-value enum
    ConflictSeverity            closed 2-value enum (HARD/SOFT)
    RecommendationAction        closed 5-value enum
    ConflictFinding             frozen audit record

Sufficiency (``core/evidence_sufficiency/sufficiency/``):
    ContextSufficiencyAgent     orchestration-facing façade
    SufficiencyDecisionEngine   pure 12-rule policy engine
    SufficiencyDecision         closed 7-value enum
    SufficiencyReport           frozen per-run decision record

Downstream subpackages (phases 4-5, not yet populated):
    verifier/                   SetLevelEvidenceVerifier
    uncertainty/                UncertaintyScoringEngine +
                                PopulationEvidenceBiasDetector

Integration surface
-------------------
Off by default. The orchestrator reads a ``sufficiency_enabled`` flag
(phase 6) before invoking ``ContextSufficiencyAgent.evaluate``.
Existing flagship demos retain their exact runtime signatures until
they opt in.

Positioning
-----------
*Evidence-governed genomic intelligence infrastructure.*
"""

from __future__ import annotations

from core.evidence_sufficiency.checkpoint import (
    CheckpointResult,
    SufficiencyCheckpoint,
)
from core.evidence_sufficiency.conflict import (
    ConflictDetectionAgent,
    ConflictFinding,
    ConflictKind,
    ConflictSeverity,
    RecommendationAction,
)
from core.evidence_sufficiency.coverage import (
    ALL_DIMENSIONS,
    ALL_FACETS,
    ClaimCoverageAnalysis,
    ClaimEvidenceFacet,
    DimensionState,
    EvidenceCoverageAnalyzer,
    FacetCoverageState,
    ProvenanceCoverageReport,
    ProvenanceCoverageTracker,
    ProvenanceDimension,
)
from core.evidence_sufficiency.sufficiency import (
    ContextSufficiencyAgent,
    SufficiencyDecision,
    SufficiencyDecisionEngine,
    SufficiencyReport,
)
from core.evidence_sufficiency.trace import (
    EvidenceSufficiencyTrace,
    RetrievalRoundRecord,
)
from core.evidence_sufficiency.uncertainty import (
    BiasFinding,
    BiasKind,
    PopulationEvidenceBiasDetector,
    UncertaintyAction,
    UncertaintyAwareReasoningLayer,
    UncertaintyReading,
    UncertaintyScore,
    UncertaintyScoringEngine,
)
from core.evidence_sufficiency.verifier import (
    EvidenceVerdict,
    EvidenceVerificationResult,
    SetLevelEvidenceVerifier,
)

__all__ = [
    # checkpoint (orchestrator façade)
    "CheckpointResult",
    "SufficiencyCheckpoint",
    # coverage
    "ClaimCoverageAnalysis",
    "ClaimEvidenceFacet",
    "FacetCoverageState",
    "ALL_FACETS",
    "EvidenceCoverageAnalyzer",
    "ProvenanceCoverageTracker",
    "ProvenanceCoverageReport",
    "ProvenanceDimension",
    "DimensionState",
    "ALL_DIMENSIONS",
    # conflict
    "ConflictDetectionAgent",
    "ConflictFinding",
    "ConflictKind",
    "ConflictSeverity",
    "RecommendationAction",
    # sufficiency
    "ContextSufficiencyAgent",
    "SufficiencyDecision",
    "SufficiencyDecisionEngine",
    "SufficiencyReport",
    # verifier
    "EvidenceVerdict",
    "EvidenceVerificationResult",
    "SetLevelEvidenceVerifier",
    # uncertainty
    "BiasFinding",
    "BiasKind",
    "PopulationEvidenceBiasDetector",
    "UncertaintyAction",
    "UncertaintyAwareReasoningLayer",
    "UncertaintyReading",
    "UncertaintyScore",
    "UncertaintyScoringEngine",
    # trace
    "EvidenceSufficiencyTrace",
    "RetrievalRoundRecord",
]
