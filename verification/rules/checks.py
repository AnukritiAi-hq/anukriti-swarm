"""Verification check implementations.

Each check validates one aspect of an agent's output:
- Evidence grounding: claims must cite sources
- Deterministic boundary: deterministic outputs must be reproducible
- Provenance: source attribution must be valid
- Guideline conflict: detect contradicting recommendations
- Sparse data: flag insufficient population evidence
- Hallucination hooks: detect unsupported claims

Every check returns a CheckResult with pass/fail/warn verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


@dataclass(frozen=True)
class CheckResult:
    """Result of a single verification check."""

    check_name: str
    verdict: Verdict
    reason: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def check_evidence_grounding(claims: list[dict[str, Any]]) -> CheckResult:
    """Verify every claim has at least one citation.

    Fails if any claim lacks supporting evidence.
    """
    ungrounded = [c for c in claims if not c.get("citations")]
    if not ungrounded:
        return CheckResult("evidence_grounding", Verdict.PASS, "All claims cite sources.")
    return CheckResult(
        "evidence_grounding", Verdict.FAIL,
        f"{len(ungrounded)}/{len(claims)} claims lack citations.",
        details={"ungrounded_count": len(ungrounded)},
    )


def check_deterministic_boundary(output: dict[str, Any]) -> CheckResult:
    """Verify deterministic outputs are not marked as generative.

    Warns if an output claims deterministic origin but has low confidence.
    """
    origin = output.get("origin", "deterministic")
    confidence = output.get("confidence", 1.0)

    if origin == "deterministic" and confidence < 0.9:
        return CheckResult(
            "deterministic_boundary", Verdict.WARN,
            f"Deterministic output has low confidence ({confidence:.2f}). Verify rule correctness.",
            details={"origin": origin, "confidence": confidence},
        )
    if origin == "generative" and confidence >= 1.0:
        return CheckResult(
            "deterministic_boundary", Verdict.WARN,
            "Generative output claims perfect confidence. Suspicious.",
            details={"origin": origin, "confidence": confidence},
        )
    return CheckResult("deterministic_boundary", Verdict.PASS, "Origin/confidence consistent.")


def check_provenance(output: dict[str, Any]) -> CheckResult:
    """Verify source attribution is present and non-empty."""
    source = output.get("source") or output.get("guideline_source")
    if not source:
        return CheckResult(
            "provenance", Verdict.FAIL,
            "No source attribution found.",
        )
    return CheckResult("provenance", Verdict.PASS, f"Source: {source}")


def check_guideline_conflict(recommendations: list[dict[str, Any]]) -> CheckResult:
    """Detect conflicting recommendations for the same drug.

    Fails if two recommendations for the same drug give contradictory actions.
    """
    by_drug: dict[str, list[str]] = {}
    for rec in recommendations:
        drug = rec.get("drug", "")
        action = rec.get("recommendation", "")
        by_drug.setdefault(drug, []).append(action)

    conflicts = []
    for drug, actions in by_drug.items():
        if len(set(actions)) > 1:
            conflicts.append(drug)

    if conflicts:
        return CheckResult(
            "guideline_conflict", Verdict.FAIL,
            f"Conflicting recommendations for: {', '.join(conflicts)}",
            details={"conflicting_drugs": conflicts},
        )
    return CheckResult("guideline_conflict", Verdict.PASS, "No guideline conflicts detected.")


def check_sparse_population_data(
    population: str, sample_n: int | None, frequency: float | None
) -> CheckResult:
    """Flag insufficient population evidence.

    Warns if sample size is small or frequency data is missing.
    """
    if frequency is None:
        return CheckResult(
            "sparse_population_data", Verdict.FAIL,
            f"No frequency data for population {population}.",
            details={"population": population},
        )
    if sample_n is not None and sample_n < 500:
        return CheckResult(
            "sparse_population_data", Verdict.WARN,
            f"Small sample size (n={sample_n}) for {population}. Interpret with caution.",
            details={"population": population, "sample_n": sample_n},
        )
    return CheckResult("sparse_population_data", Verdict.PASS, f"Adequate data for {population}.")


def check_hallucination_hooks(output: dict[str, Any], known_genes: set[str], known_drugs: set[str]) -> CheckResult:
    """Detect potential hallucinated entities.

    Warns if output references genes or drugs not in known databases.
    """
    gene = output.get("gene", "")
    drug = output.get("drug", "")
    issues = []

    if gene and gene not in known_genes:
        issues.append(f"Unknown gene: {gene}")
    if drug and drug not in known_drugs:
        issues.append(f"Unknown drug: {drug}")

    if issues:
        return CheckResult(
            "hallucination_detection", Verdict.WARN,
            f"Potential hallucination: {'; '.join(issues)}",
            details={"issues": issues},
        )
    return CheckResult("hallucination_detection", Verdict.PASS, "All entities recognized.")
