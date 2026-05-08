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


# ---------------------------------------------------------------------------
# Orchestration-layer prompts
# ---------------------------------------------------------------------------
#
# These prompts are consumed by ``core.orchestrator.planner.WorkflowPlanner``
# and ``agents.orchestrator.gemini_orchestrator.GeminiOrchestrator``.
#
# Gemini is used here ONLY for:
#   - decomposing a query into substeps (planning)
#   - suggesting which specialist agents to activate (advisory routing)
#   - producing a high-level reasoning summary of what the swarm did
#   - comparative narrative across populations / drugs
#
# Gemini is NEVER asked for a phenotype, recommendation, or any other
# biomedical fact — those flow from the deterministic specialists.
# ``GenerativeBoundary`` enforces that at runtime.

# Machine-readable substep vocabulary the planner is allowed to emit.
# Keep in sync with ``AgentRouter`` role mapping.
ORCHESTRATION_SUBSTEPS = (
    "population_analysis",   # deterministic — population agent
    "pharmacogene_analysis", # deterministic — CYP/HLA specialist
    "evidence_retrieval",    # deterministic — MA-RAG pipeline
    "verification",          # deterministic — verification engine
    "comparative_analysis",  # orchestrator fan-out (multi-pop / multi-drug)
    "narrative_synthesis",   # generative — audience-specific explanation
)


def orchestration_plan(ctx: dict[str, Any]) -> str:
    """Prompt Gemini to decompose a query into ordered substeps.

    The LLM MUST return a JSON array of step objects of the form::

        [
          {"step": 1, "action": "population_analysis", "reason": "..."},
          {"step": 2, "action": "pharmacogene_analysis", "reason": "..."},
          ...
        ]

    The planner validates the JSON and falls back to a deterministic
    plan when the model is unavailable or emits malformed output.
    """
    allowed = ", ".join(ORCHESTRATION_SUBSTEPS)
    populations = ctx.get("populations") or ([ctx["population"]] if ctx.get("population") else [])
    drugs = ctx.get("drugs") or ([ctx["drug"]] if ctx.get("drug") else [])
    return f"""{SYSTEM_CONTEXT}

TASK: Plan — decompose the following pharmacogenomic query into an
ordered list of orchestration substeps. You are NOT answering the
biomedical question; you are only deciding which specialists should
run, in what order, and why.

QUERY: {ctx.get('query', '')}
Gene: {ctx.get('gene', '(unspecified)')}
Diplotype: {ctx.get('diplotype', '(unspecified)')}
Drug(s): {', '.join(drugs) or '(unspecified)'}
Population(s): {', '.join(populations) or '(unspecified)'}
Comparative run: {bool(len(populations) > 1 or len(drugs) > 1)}

ALLOWED ACTIONS (use these exact strings): {allowed}

RULES:
- Output a JSON array only. No prose before or after.
- Every step MUST have: step (int), action (one of the allowed values), reason (short string).
- Deterministic substeps must come BEFORE narrative_synthesis.
- verification must come BEFORE narrative_synthesis.
- For multi-population or multi-drug queries include comparative_analysis
  before narrative_synthesis.
- Keep the plan minimal: do not add substeps that aren't needed for this query.

Return only the JSON array."""


def orchestration_synthesis(ctx: dict[str, Any]) -> str:
    """Prompt Gemini to produce a high-level summary of the swarm run.

    Distinct from ``orchestration_summary`` (which focuses on the
    reasoning chain); this one is specifically about *the execution
    itself* — what the orchestrator did, in what order, and whether
    verification passed. Used for audit-facing narratives.
    """
    return f"""{SYSTEM_CONTEXT}

TASK: Summarize this orchestration run for an audit reader. Explain:
1. What the query asked for.
2. Which specialist agents were activated and why.
3. What the deterministic layer concluded (phenotype, recommendation).
4. Whether verification passed, and what grounded the claims.

DO NOT repeat CPIC recommendations verbatim beyond a single sentence.
DO NOT invent citations — use only the ones provided. Keep under 180 words.

RUN METADATA:
{_format_context(ctx)}
Agents activated: {ctx.get('agents', [])}
Verification: {ctx.get('verification', 'unknown')}
Evidence citations: {ctx.get('citations', [])}"""


def orchestration_comparative(ctx: dict[str, Any]) -> str:
    """Prompt Gemini to produce a comparative narrative across fan-outs.

    Used when the orchestrator fans out across multiple populations
    (or drugs). The per-run data is already in ``ctx['comparison_rows']``
    as a list of ``{label, phenotype, risk, frequency, recommendation}``
    dicts derived from the deterministic results.
    """
    rows = ctx.get("comparison_rows", [])
    rendered = "\n".join(
        f"- {r.get('label','?')}: phenotype={r.get('phenotype','?')}, "
        f"risk={r.get('risk','?')}, freq={r.get('frequency','?')}, "
        f"recommendation={r.get('recommendation','?')}"
        for r in rows
    ) or "(no rows provided)"
    return f"""{SYSTEM_CONTEXT}

TASK: Write a comparative narrative across the rows below. Explain why
the clinical implications differ across populations or drugs. Highlight
equity-relevant differences (e.g. guideline-vs-actual-population gap)
when the data supports it. Ground every claim in the provided rows.
Keep under 200 words. Do NOT invent values not present in the rows.

GENE: {ctx.get('gene', '(unspecified)')}
DRUG(S): {ctx.get('drugs') or ctx.get('drug', '(unspecified)')}

COMPARISON ROWS:
{rendered}"""
