"""Report section templates — deterministic vs narrative separation.

Templates enforce the boundary between established facts and
narrative explanations. Each template marks its origin clearly.
"""

from __future__ import annotations

from narrative.engine import NarrativeSection


def deterministic_finding(gene: str, diplotype: str, phenotype: str, score: float, source: str) -> NarrativeSection:
    """Template for a deterministic genotype finding."""
    return NarrativeSection(
        title=f"{gene} Genotype",
        content=f"Diplotype: {diplotype} | Activity Score: {score} | Phenotype: {phenotype}",
        origin="deterministic", citations=[source], confidence=1.0,
    )


def population_context(population: str, allele: str, frequency: float, rarity: str, source: str) -> NarrativeSection:
    """Template for population frequency context."""
    return NarrativeSection(
        title="Population Context",
        content=f"{allele} frequency in {population}: {frequency:.1%} ({rarity})",
        origin="deterministic", citations=[source], confidence=0.95,
    )


def recommendation(drug: str, action: str, strength: str, guideline_id: str, pmid: str) -> NarrativeSection:
    """Template for a clinical recommendation."""
    return NarrativeSection(
        title=f"Recommendation: {drug}",
        content=f"[{strength.upper()}] {action}",
        origin="deterministic", citations=[pmid, guideline_id], confidence=1.0,
    )


def uncertainty_note(note: str) -> NarrativeSection:
    """Template for explicit uncertainty communication."""
    return NarrativeSection(
        title="Limitations & Uncertainty",
        content=note,
        origin="narrative", confidence=1.0,
        uncertainty_note=note,
    )


def escalation_marker(tier: str, reason: str) -> NarrativeSection:
    """Template for escalation markers in the report."""
    return NarrativeSection(
        title="⚠️ Escalation",
        content=f"Tier: {tier} | {reason}",
        origin="deterministic", confidence=1.0,
    )


def verification_summary(verdict: str, confidence: float, level: str, checks_passed: int, checks_total: int) -> NarrativeSection:
    """Template for verification status summary."""
    return NarrativeSection(
        title="Verification",
        content=f"Verdict: {verdict.upper()} | Confidence: {confidence:.3f} ({level}) | Checks: {checks_passed}/{checks_total}",
        origin="deterministic", confidence=confidence,
    )
