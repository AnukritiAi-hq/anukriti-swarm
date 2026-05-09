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

On the output side it emits a single ``SufficiencyDecision`` that
the orchestrator honours *before* any generative narrative runs.

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

Sub-packages
------------
    sufficiency/   ContextSufficiencyAgent, SufficiencyDecisionEngine
    coverage/      EvidenceCoverageAnalyzer, ProvenanceCoverageTracker,
                   ClaimCoverageAnalysis
    conflict/      ConflictDetectionAgent
    uncertainty/   UncertaintyScoringEngine, UncertaintyScore,
                   PopulationEvidenceBiasDetector
    verifier/      SetLevelEvidenceVerifier, EvidenceVerificationResult
    trace.py       EvidenceSufficiencyTrace (frozen audit record)

Integration surface
-------------------
Off by default. The orchestrator reads a ``sufficiency_enabled`` flag
(phase 6) before invoking the checkpoint. Existing demos retain their
exact runtime signatures until they opt in.

Positioning
-----------
*Evidence-governed genomic intelligence infrastructure.*
"""

from __future__ import annotations

__all__: list[str] = []
