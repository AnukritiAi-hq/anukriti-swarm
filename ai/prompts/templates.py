"""Prompt templates for audience-specific generation.

Every prompt receives ONLY deterministic outputs as input.
Gemini explains what the deterministic system already decided.

Template structure:
- System context (role, constraints, safety boundaries)
- Deterministic findings (the truth to explain)
- Evidence references (what to cite)
- Audience instruction (how to communicate)
"""

from __future__ import annotations

from typing import Any


def _format_context(ctx: dict[str, Any]) -> str:
    """Format deterministic context into prompt-ready text."""
    lines = []
    if ctx.get("gene"):
        lines.append(f"Gene: {ctx['gene']}")
    if ctx.get("diplotype"):
        lines.append(f"Diplotype: {ctx['diplotype']}")
    if ctx.get("phenotype"):
        lines.append(f"Phenotype: {ctx['phenotype']} [DETERMINISTIC — this is established fact]")
    if ctx.get("risk"):
        lines.append(f"Risk classification: {ctx['risk']}")
    if ctx.get("drug"):
        lines.append(f"Drug: {ctx['drug']}")
    if ctx.get("recommendation"):
        lines.append(f"CPIC Recommendation: {ctx['recommendation']}")
    if ctx.get("population"):
        lines.append(f"Population: {ctx['population']}")
    if ctx.get("frequency"):
        lines.append(f"Allele frequency in population: {ctx['frequency']}")
    if ctx.get("citations"):
        lines.append(f"Evidence: {', '.join(ctx['citations'])}")
    if ctx.get("confidence"):
        lines.append(f"Confidence: {ctx['confidence']}")
    if ctx.get("verification"):
        lines.append(f"Verification: {ctx['verification']}")
    return "\n".join(lines)


SYSTEM_CONTEXT = """You are a pharmacogenomics explanation assistant within the Anukriti Swarm system.

CRITICAL RULES:
- You EXPLAIN deterministic findings. You do NOT make biomedical decisions.
- Every claim you make must reference the provided evidence.
- Do NOT infer phenotypes, recommend drugs, or override the deterministic analysis.
- If the deterministic system says "Poor Metabolizer" — that is FACT. Explain it, don't question it.
- Always note this is research output, not clinical advice.
- Cite the provided PMIDs and guideline IDs."""


def clinician_explanation(ctx: dict[str, Any]) -> str:
    """Prompt for clinician-friendly explanation."""
    return f"""{SYSTEM_CONTEXT}

DETERMINISTIC FINDINGS (authoritative — do not override):
{_format_context(ctx)}

TASK: Generate a concise clinician-friendly explanation of these findings.
Include: clinical significance, mechanism, population context, and recommended action.
Cite the evidence. Use professional medical language. Keep under 150 words."""


def patient_explanation(ctx: dict[str, Any]) -> str:
    """Prompt for patient-friendly explanation."""
    return f"""{SYSTEM_CONTEXT}

DETERMINISTIC FINDINGS (authoritative — do not override):
{_format_context(ctx)}

TASK: Explain these findings to a patient with no medical background.
Use simple language. Avoid jargon. Focus on what this means for them practically.
Include what they should discuss with their doctor.
Do NOT provide medical advice. Note this is research information only. Keep under 120 words."""


def research_explanation(ctx: dict[str, Any]) -> str:
    """Prompt for research-focused explanation."""
    return f"""{SYSTEM_CONTEXT}

DETERMINISTIC FINDINGS (authoritative — do not override):
{_format_context(ctx)}

TASK: Generate a research-grade explanation suitable for a pharmacogenomics paper.
Include: genotype-phenotype relationship, activity score rationale, population epidemiology,
guideline evidence level, and clinical implications.
Cite all provided evidence. Use scientific terminology. Keep under 200 words."""


def population_comparison(ctx: dict[str, Any]) -> str:
    """Prompt for comparative population analysis."""
    return f"""{SYSTEM_CONTEXT}

DETERMINISTIC FINDINGS (authoritative — do not override):
{_format_context(ctx)}

POPULATION DATA:
{ctx.get('population_data', 'No additional population data provided.')}

TASK: Explain why this finding has different clinical significance across populations.
Discuss allele frequency variation, prevalence differences, and health equity implications.
Ground every claim in the provided data. Keep under 180 words."""


def orchestration_summary(ctx: dict[str, Any]) -> str:
    """Prompt for orchestration reasoning summary."""
    return f"""{SYSTEM_CONTEXT}

PIPELINE EXECUTION:
{_format_context(ctx)}

Agents involved: {ctx.get('agents', [])}
Stages completed: {ctx.get('stages', [])}
Verification: {ctx.get('verification', 'unknown')}

TASK: Summarize what the swarm did and why. Explain the reasoning chain:
which agents contributed what, how evidence was grounded, and why the
verification passed. Keep under 100 words. Use technical but clear language."""
