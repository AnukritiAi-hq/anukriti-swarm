"""Confidence thresholds and uncertainty propagation.

Defines confidence scoring rules and propagation logic:
- Each pipeline stage contributes a confidence factor
- Final confidence is the product of all stage confidences
- Thresholds determine whether output is accepted, flagged, or rejected

Uncertainty propagation: if any upstream stage has low confidence,
downstream stages inherit that uncertainty (it never increases).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ConfidenceLevel(str, Enum):
    """Confidence classification for routing decisions."""

    HIGH = "high"           # ≥ 0.85 — autonomous delivery
    MODERATE = "moderate"   # 0.60–0.85 — multi-agent review
    LOW = "low"             # 0.30–0.60 — escalation recommended
    INSUFFICIENT = "insufficient"  # < 0.30 — reject/escalate


# Thresholds
THRESHOLD_HIGH = 0.85
THRESHOLD_MODERATE = 0.60
THRESHOLD_LOW = 0.30


@dataclass(frozen=True)
class ConfidenceScore:
    """A confidence score with provenance."""

    value: float
    level: ConfidenceLevel
    source: str             # Which stage/check produced this
    factors: dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def classify_confidence(value: float) -> ConfidenceLevel:
    """Classify a confidence value into a level."""
    if value >= THRESHOLD_HIGH:
        return ConfidenceLevel.HIGH
    if value >= THRESHOLD_MODERATE:
        return ConfidenceLevel.MODERATE
    if value >= THRESHOLD_LOW:
        return ConfidenceLevel.LOW
    return ConfidenceLevel.INSUFFICIENT


def propagate_confidence(stage_confidences: dict[str, float]) -> ConfidenceScore:
    """Propagate uncertainty through pipeline stages.

    Final confidence = product of all stage confidences.
    This ensures that low confidence in any stage reduces overall confidence.

    Example:
        phenotype_inference: 1.0 (deterministic)
        population_data: 0.80 (moderate sample size)
        evidence_retrieval: 0.90 (good relevance)
        → final: 1.0 × 0.80 × 0.90 = 0.72 (moderate)
    """
    if not stage_confidences:
        return ConfidenceScore(
            value=0.0, level=ConfidenceLevel.INSUFFICIENT,
            source="no_stages", factors={},
        )

    final = 1.0
    for value in stage_confidences.values():
        final *= value

    final = round(final, 4)
    level = classify_confidence(final)

    return ConfidenceScore(
        value=final, level=level,
        source="propagated",
        factors=stage_confidences,
    )


def minimum_confidence(stage_confidences: dict[str, float]) -> ConfidenceScore:
    """Alternative: use minimum confidence (most conservative).

    Useful when any single weak link should dominate the assessment.
    """
    if not stage_confidences:
        return ConfidenceScore(
            value=0.0, level=ConfidenceLevel.INSUFFICIENT,
            source="no_stages", factors={},
        )

    min_val = min(stage_confidences.values())
    min_source = min(stage_confidences, key=stage_confidences.get)  # type: ignore[arg-type]

    return ConfidenceScore(
        value=round(min_val, 4),
        level=classify_confidence(min_val),
        source=f"min_from_{min_source}",
        factors=stage_confidences,
    )
