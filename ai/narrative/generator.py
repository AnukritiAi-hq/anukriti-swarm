"""Gemini-powered explanation generation from deterministic outputs.

Takes verified, deterministic pipeline results and generates
audience-specific explanations. The AI layer ONLY explains —
it never decides, overrides, or generates unsupported claims.

Architecture:
  Deterministic Core → verified results → Gemini → explanation
  (authoritative)      (grounded input)   (cognition)  (labeled output)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ai.gemini.client import GeminiClient, GeminiResponse
from ai.prompts.templates import (
    clinician_explanation,
    patient_explanation,
    population_comparison,
    research_explanation,
)


@dataclass
class GeneratedExplanation:
    """An AI-generated explanation with full provenance."""

    audience: str
    text: str
    grounded: bool
    model: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    input_context: dict[str, Any]
    origin: str = "generative"  # Always labeled
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NarrativeGenerator:
    """Generates audience-specific explanations from deterministic outputs.

    Safety boundaries:
    - Input MUST be verified deterministic outputs
    - Output is ALWAYS labeled as 'generative'
    - Grounding is checked on every response
    - Ungrounded responses are flagged
    """

    def __init__(self, client: GeminiClient | None = None) -> None:
        self.client = client or GeminiClient()

    def explain_for_clinician(self, ctx: dict[str, Any]) -> GeneratedExplanation:
        """Generate clinician-friendly explanation."""
        prompt = clinician_explanation(ctx)
        return self._generate("clinician", prompt, ctx)

    def explain_for_patient(self, ctx: dict[str, Any]) -> GeneratedExplanation:
        """Generate patient-friendly explanation."""
        prompt = patient_explanation(ctx)
        return self._generate("patient", prompt, ctx)

    def explain_for_research(self, ctx: dict[str, Any]) -> GeneratedExplanation:
        """Generate research-focused explanation."""
        prompt = research_explanation(ctx)
        return self._generate("research", prompt, ctx)

    def explain_population_context(self, ctx: dict[str, Any]) -> GeneratedExplanation:
        """Generate population comparison explanation."""
        prompt = population_comparison(ctx)
        return self._generate("population_comparison", prompt, ctx)

    def _generate(self, audience: str, prompt: str, ctx: dict[str, Any]) -> GeneratedExplanation:
        """Core generation with grounding validation."""
        response = self.client.generate(prompt, context=ctx)

        return GeneratedExplanation(
            audience=audience,
            text=response.text,
            grounded=response.grounded,
            model=response.model,
            latency_ms=response.latency_ms,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            input_context=ctx,
        )
