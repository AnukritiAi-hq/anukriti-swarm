"""Evidence Sufficiency — ``uncertainty/`` subpackage.

Hosts the epistemic-uncertainty primitives added in phase 5 of the
brief. Responsibilities:

    UncertaintyScore               4-tier closed enum
                                   (low / moderate / high / unsafe)
                                   (commit 14)
    UncertaintyAction              5-value closed enum
                                   (proceed / request_more / abstain
                                   / escalate / block)  (commit 14)
    UncertaintyReading             frozen per-run uncertainty record
                                   (commit 14)
    UncertaintyScoringEngine       deterministic 9-rule score from
                                   coverage + conflict + pathway
                                   (commit 14)
    UncertaintyAwareReasoningLayer thin policy wrapper mapping tier
                                   to action (commit 14)
    PopulationEvidenceBiasDetector flags Eurocentric imbalance,
                                   ancestry scarcity, unsupported
                                   cross-population extrapolation
                                   (commit 15)

All components are deterministic: no sampling, no LLM, no randomness.
The score is a closed-form function of the analyzer outputs so two
identical inputs always produce the same score.
"""

from __future__ import annotations

from core.evidence_sufficiency.uncertainty.engine import (
    UncertaintyAction,
    UncertaintyAwareReasoningLayer,
    UncertaintyReading,
    UncertaintyScore,
    UncertaintyScoringEngine,
)

__all__ = [
    "UncertaintyAction",
    "UncertaintyAwareReasoningLayer",
    "UncertaintyReading",
    "UncertaintyScore",
    "UncertaintyScoringEngine",
]
