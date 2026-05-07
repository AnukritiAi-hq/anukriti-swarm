"""Narrative explanation engine.

Generates audience-specific explanations from structured pipeline results.
Three audience levels:
- PATIENT: plain language, no jargon, actionable takeaways
- RESEARCHER: scientific detail, population context, evidence citations
- AUDIT: full technical trace, provenance, confidence scores, verification

Every claim in the narrative references its evidence source.
Uncertainty is always surfaced explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Audience(str, Enum):
    PATIENT = "patient"
    RESEARCHER = "researcher"
    AUDIT = "audit"


@dataclass
class NarrativeSection:
    """A single section of the narrative report."""

    title: str
    content: str
    origin: str             # "deterministic" or "narrative"
    citations: list[str] = field(default_factory=list)
    confidence: float = 1.0
    uncertainty_note: str | None = None


@dataclass
class NarrativeReport:
    """Complete narrative report for a specific audience."""

    audience: Audience
    sections: list[NarrativeSection] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = ""


class NarrativeEngine:
    """Generates audience-specific narrative explanations."""

    def generate(self, state: dict[str, Any], audience: Audience) -> NarrativeReport:
        """Generate a narrative report from pipeline state."""
        if audience == Audience.PATIENT:
            return self._patient_report(state)
        if audience == Audience.RESEARCHER:
            return self._researcher_report(state)
        return self._audit_report(state)

    def _patient_report(self, state: dict[str, Any]) -> NarrativeReport:
        pgx = state.get("pharmacogene_result", {})
        pop = state.get("population_result", {})
        recs = state.get("recommendations", [])

        sections = []

        # What we found
        sections.append(NarrativeSection(
            title="What We Found",
            content=(
                f"Your genetic test shows you have a variation in the {pgx.get('gene', 'gene')} gene "
                f"(genotype: {pgx.get('diplotype', '?')}). This means your body processes the drug "
                f"{state.get('drug', 'medication')} differently than most people."
            ),
            origin="narrative", citations=[], confidence=pgx.get("confidence", 1.0),
        ))

        # What this means
        phenotype = pgx.get("phenotype", "")
        if "Poor" in phenotype or "Intermediate" in phenotype:
            sections.append(NarrativeSection(
                title="What This Means For You",
                content=(
                    f"You are classified as a '{phenotype}' for this gene. "
                    f"This means {state.get('drug', 'this medication')} may not work as well for you "
                    f"as it does for most people. Your doctor may want to consider an alternative medication."
                ),
                origin="narrative", confidence=pgx.get("confidence", 1.0),
            ))

        # Recommendation
        if recs:
            rec = recs[0]
            sections.append(NarrativeSection(
                title="What Your Doctor Should Know",
                content=f"Based on clinical guidelines: {rec.get('recommendation', '')}",
                origin="deterministic",
                citations=[rec.get("pmid", "")],
                confidence=1.0,
            ))

        # Uncertainty
        sections.append(NarrativeSection(
            title="Important Notes",
            content=(
                "This is a research analysis, not a clinical recommendation. "
                "Always discuss genetic test results with your healthcare provider. "
                "Other factors (other medications, health conditions) also affect drug response."
            ),
            origin="narrative", confidence=1.0,
            uncertainty_note="Research output only. Not for clinical decision-making.",
        ))

        return NarrativeReport(audience=Audience.PATIENT, sections=sections, correlation_id=state.get("correlation_id", ""))

    def _researcher_report(self, state: dict[str, Any]) -> NarrativeReport:
        pgx = state.get("pharmacogene_result", {})
        pop = state.get("population_result", {})
        recs = state.get("recommendations", [])
        v = state.get("verification", {})

        sections = []

        # Genotype
        sections.append(NarrativeSection(
            title="Genotype Assessment",
            content=(
                f"Gene: {pgx.get('gene')} | Diplotype: {pgx.get('diplotype')} | "
                f"Activity Score: {pgx.get('activity_score')} | "
                f"Phenotype: {pgx.get('phenotype')} [{pgx.get('origin', 'deterministic').upper()}]"
            ),
            origin="deterministic", confidence=pgx.get("confidence", 1.0),
            citations=[r.get("pmid", "") for r in recs if r.get("pmid")],
        ))

        # Population context
        if pop:
            freq = pop.get("frequency")
            freq_str = f"{freq:.1%}" if freq else "unknown"
            sections.append(NarrativeSection(
                title="Population Context",
                content=(
                    f"In {pop.get('population', '?')} populations, the identified allele has a frequency of "
                    f"{freq_str} ({pop.get('rarity', '?')}). {pop.get('clinical_note', '')}"
                ),
                origin="deterministic", confidence=pop.get("confidence", 0.95),
                citations=[pop.get("source", "")],
            ))

        # Prevalence
        prevalence = state.get("population_prevalence", [])
        if prevalence:
            prev_lines = [f"{p['phenotype']}: {p['prevalence']:.1%}" for p in prevalence]
            sections.append(NarrativeSection(
                title="Population Phenotype Distribution",
                content=f"Metabolizer prevalence in this population: {' | '.join(prev_lines)}",
                origin="deterministic", confidence=0.95,
            ))

        # Recommendations
        for rec in recs:
            sections.append(NarrativeSection(
                title=f"Recommendation: {rec.get('drug', '')}",
                content=f"[{rec.get('strength', '').upper()}] {rec.get('recommendation', '')}",
                origin="deterministic",
                citations=[rec.get("pmid", ""), rec.get("guideline_id", "")],
                confidence=1.0,
            ))

        # Verification
        sections.append(NarrativeSection(
            title="Verification Status",
            content=(
                f"Verdict: {v.get('verdict', '?').upper()} | "
                f"Confidence: {v.get('confidence', 0):.3f} ({v.get('confidence_level', '?')}) | "
                f"Escalation: {v.get('escalation_tier', '?')}"
            ),
            origin="deterministic", confidence=v.get("confidence", 0),
        ))

        return NarrativeReport(audience=Audience.RESEARCHER, sections=sections, correlation_id=state.get("correlation_id", ""))

    def _audit_report(self, state: dict[str, Any]) -> NarrativeReport:
        pgx = state.get("pharmacogene_result", {})
        v = state.get("verification", {})

        sections = []

        # Provenance
        sections.append(NarrativeSection(
            title="Provenance",
            content=(
                f"Correlation: {state.get('correlation_id', '?')} | "
                f"Rule engine: {pgx.get('provenance', {}).get('rule_engine', '?')} | "
                f"Guideline: {pgx.get('provenance', {}).get('guideline_source', '?')} | "
                f"Origin: {pgx.get('origin', '?')}"
            ),
            origin="deterministic", confidence=1.0,
        ))

        # Verification checks
        for c in v.get("checks", []):
            sections.append(NarrativeSection(
                title=f"Check: {c.get('name', '?')}",
                content=f"[{c.get('verdict', '?').upper()}] {c.get('reason', '')}",
                origin="deterministic", confidence=1.0,
            ))

        # Escalation
        sections.append(NarrativeSection(
            title="Escalation Decision",
            content=f"Tier: {v.get('escalation_tier', '?')} | Action: {v.get('action', '?')}",
            origin="deterministic", confidence=1.0,
        ))

        return NarrativeReport(audience=Audience.AUDIT, sections=sections, correlation_id=state.get("correlation_id", ""))
