"""Evidence Sufficiency — ``uncertainty/`` subpackage.

Hosts the epistemic-uncertainty primitives added in phase 5 of the
brief. Responsibilities:

    UncertaintyScore               4-tier closed enum
                                   (low / moderate / high / unsafe)
    UncertaintyScoringEngine       deterministic score derived from
                                   coverage, conflict, and population
                                   representation
    UncertaintyAwareReasoningLayer policy wrapper that turns an
                                   UncertaintyScore into an action
                                   (proceed / request / abstain /
                                   escalate / block)
    PopulationEvidenceBiasDetector flags Eurocentric imbalance,
                                   ancestry scarcity, unsupported
                                   cross-population extrapolation

All four are deterministic: no sampling, no LLM, no randomness.
The score is a closed-form function of the analyzer outputs so two
identical inputs always produce the same score.
"""

from __future__ import annotations

__all__: list[str] = []
