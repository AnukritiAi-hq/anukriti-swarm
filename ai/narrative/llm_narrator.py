"""T8 — LLMNarrator: chemistry-grounded narrative synthesis.

Takes deterministic pipeline outputs + retrieval results, builds a
structured grounding context (including anukriti-chemistry drug data),
calls the LLM with a frozen grounding prompt, validates citations via
CitationValidator, and returns a guarded LLMNarrative.

Scope firewall: this is the ONLY place anukriti-chemistry is imported
in the swarm. The deterministic layers (pharmacogene, runtime,
evidence_sufficiency, orchestrator) MUST NOT import chemistry.

Off-by-default; opt-in via SwarmRuntime(llm_narrator=LLMNarrator(...)).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.orchestrator.boundary import GenerativeAction, GenerativeBoundary
from core.runtime.citation_validator import (
    CitationValidator,
    CitationValidationTrace,
    CitationVerdict,
)


@dataclass(frozen=True)
class LLMNarrative:
    """Validated LLM-generated narrative with citations and trace."""

    text: str
    citations: tuple[str, ...]
    validation: CitationValidationTrace
    chemistry_context: dict[str, Any]
    model: str
    latency_ms: float
    origin: str = "generative_grounded"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# Frozen grounding prompt — never modified at runtime.
_GROUNDING_PROMPT = """\
You are a pharmacogenomics research narrator. Reason ONLY from the data below.

RULES:
1. Every factual claim MUST end with a citation in the form [Source, ID] \
referencing one of the provided evidence records.
2. Do NOT introduce drugs, genes, or recommendations not present in the data.
3. Do NOT infer phenotypes — report them exactly as given.
4. Do NOT override or soften CPIC recommendations.
5. If evidence is insufficient, say so explicitly — do not speculate.

CONTEXT:
{context}

TASK: Write a concise, evidence-grounded explanation for a {audience} audience.
"""


def _load_chemistry_context(drug: str) -> dict[str, Any]:
    """Load chemistry grounding data for a drug. Never raises."""
    ctx: dict[str, Any] = {"drug": drug}
    try:
        from anukriti_chemistry.smiles import lookup as smiles_lookup
        result = smiles_lookup(drug)
        if result:
            ctx["smiles"] = result
    except (ImportError, Exception):
        pass

    try:
        from anukriti_chemistry.roles import get_drug_entry
        entry = get_drug_entry(drug)
        if entry:
            ctx["isomer_roles"] = {
                "active": entry.get("active_isomer", ""),
                "inactive": entry.get("inactive_isomer", ""),
                "note": entry.get("clinical_note", ""),
            }
    except (ImportError, Exception):
        pass

    return ctx


def _format_context(
    gene: str,
    drug: str,
    population: str,
    phenotype: str,
    evidence_records: list[dict[str, Any]],
    chemistry: dict[str, Any],
    recommendations: list[dict[str, Any]] | None = None,
) -> str:
    """Format the structured grounding block for the LLM."""
    lines = [
        f"Gene: {gene}",
        f"Drug: {drug}",
        f"Population: {population}",
        f"Phenotype: {phenotype} [ESTABLISHED — deterministic, do not override]",
    ]
    if chemistry.get("smiles"):
        lines.append(f"Drug SMILES: {chemistry['smiles']}")
    if chemistry.get("isomer_roles"):
        roles = chemistry["isomer_roles"]
        lines.append(f"Active isomer: {roles.get('active', 'N/A')}")
        if roles.get("note"):
            lines.append(f"Chemistry note: {roles['note']}")

    if recommendations:
        lines.append("\nCPIC Recommendations:")
        for rec in recommendations:
            lines.append(f"  - [{rec.get('strength', '?')}] {rec.get('text', rec.get('recommendation', ''))}")

    lines.append("\nEvidence Records:")
    for i, rec in enumerate(evidence_records, 1):
        source = rec.get("source", "Unknown")
        source_id = rec.get("source_id", rec.get("pmid", f"rec_{i}"))
        claim = rec.get("claim", rec.get("text", rec.get("summary", "")))
        lines.append(f"  [{source}, {source_id}]: {claim[:300]}")

    return "\n".join(lines)


class LLMNarrator:
    """Chemistry-grounded LLM narrator with citation validation.

    Args:
        client: LLM client (GeminiClient or compatible). If None, uses
            a mock that returns an empty response (for testing).
        boundary: GenerativeBoundary instance for safety checks.
        validator: CitationValidator instance.
        audience: Target audience for narration (clinician/patient/research).
    """

    def __init__(
        self,
        client: Any | None = None,
        boundary: GenerativeBoundary | None = None,
        validator: CitationValidator | None = None,
        audience: str = "clinician",
    ) -> None:
        self._client = client
        self._boundary = boundary or GenerativeBoundary()
        self._validator = validator or CitationValidator()
        self._audience = audience

    def narrate(
        self,
        *,
        gene: str,
        drug: str,
        population: str,
        phenotype: str,
        evidence_records: list[dict[str, Any]],
        recommendations: list[dict[str, Any]] | None = None,
    ) -> LLMNarrative:
        """Generate a grounded narrative with citation validation.

        Raises GenerativeBoundaryViolation if the LLM attempts a
        forbidden action (fabricated citation → FABRICATE_CLAIM).
        """
        # Guard: assert synthesis is allowed
        self._boundary.assert_allowed(
            GenerativeAction.EXPLAIN,
            "LLMNarrator performs grounded explanation synthesis.",
        )

        # Load chemistry context (never raises)
        chemistry = _load_chemistry_context(drug)

        # Build the evidence source ID set for validation
        source_ids: set[str] = set()
        for rec in evidence_records:
            if rec.get("source_id"):
                source_ids.add(rec["source_id"])
            if rec.get("pmid"):
                source_ids.add(rec["pmid"])
            if rec.get("source"):
                source_ids.add(rec["source"])

        # Format context block
        context_block = _format_context(
            gene=gene, drug=drug, population=population,
            phenotype=phenotype, evidence_records=evidence_records,
            chemistry=chemistry, recommendations=recommendations,
        )

        # Build prompt
        prompt = _GROUNDING_PROMPT.format(context=context_block, audience=self._audience)

        # Call LLM (or return empty if no client)
        import time
        t0 = time.perf_counter()

        if self._client is None:
            text = ""
            model = "none"
        else:
            response = self._client.generate(prompt)
            text = response.text if hasattr(response, "text") else str(response)
            model = getattr(response, "model", "unknown")

        latency_ms = (time.perf_counter() - t0) * 1000

        # Validate citations
        validation = self._validator.validate(text, source_ids if source_ids else None)

        # If fabricated citations detected, raise boundary violation
        if validation.verdict == CitationVerdict.FABRICATED_CITATION:
            self._boundary.assert_allowed(
                GenerativeAction.FABRICATE_CLAIM,
                f"LLM produced fabricated citations: {validation.fabricated_citations}",
            )

        # Extract citation tokens from text
        import re
        citation_re = re.compile(r"\[([^,\[\]]+),\s*([^,\[\]]+)\]")
        citations = tuple(
            f"[{m[0].strip()}, {m[1].strip()}]"
            for m in citation_re.findall(text)
        )

        return LLMNarrative(
            text=text,
            citations=citations,
            validation=validation,
            chemistry_context=chemistry,
            model=model,
            latency_ms=latency_ms,
        )
