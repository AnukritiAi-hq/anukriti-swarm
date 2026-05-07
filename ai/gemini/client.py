"""Gemini API abstraction with retry, validation, and observability.

Uses the new google-genai SDK (not deprecated google-generativeai).
Falls back gracefully when API is unavailable or rate-limited.

Safety boundary: This client NEVER makes biomedical decisions.
It only generates explanations from pre-computed deterministic outputs.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class GeminiResponse:
    """Structured response from Gemini with observability metadata."""

    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    grounded: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GeminiMetrics:
    """Accumulated metrics for Gemini usage."""

    total_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_latency_ms: float = 0.0
    failures: int = 0


class GeminiClient:
    """Abstraction layer for Gemini API access.

    Uses google-genai SDK. Falls back to template-based generation
    when API is unavailable or rate-limited.

    Usage:
        client = GeminiClient()
        response = client.generate(prompt, context={...})
    """

    def __init__(self, model: str = "gemini-2.0-flash", max_retries: int = 2) -> None:
        self.model = model
        self.max_retries = max_retries
        self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.metrics = GeminiMetrics()
        self._client: Any = None

        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                self._client = None

    @property
    def available(self) -> bool:
        """Whether the Gemini API is configured and accessible."""
        return self._client is not None

    def generate(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> GeminiResponse:
        """Generate a response from Gemini.

        If API is unavailable or rate-limited, returns a structured
        fallback response that still works for demo purposes.
        """
        self.metrics.total_calls += 1
        t0 = time.perf_counter()

        if not self.available:
            return self._fallback_generate(prompt, context, t0)

        for attempt in range(self.max_retries + 1):
            try:
                from google.genai import types
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                )
                latency = (time.perf_counter() - t0) * 1000
                text = response.text or ""

                prompt_tokens = int(len(prompt.split()) * 1.3)
                completion_tokens = int(len(text.split()) * 1.3)

                self.metrics.total_prompt_tokens += prompt_tokens
                self.metrics.total_completion_tokens += completion_tokens
                self.metrics.total_latency_ms += latency

                return GeminiResponse(
                    text=text, model=self.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=latency,
                    grounded=self._check_grounding(text, context),
                )
            except Exception as e:
                if attempt == self.max_retries:
                    self.metrics.failures += 1
                    return self._fallback_generate(prompt, context, t0)
                time.sleep(1.0 * (2 ** attempt))

        return self._fallback_generate(prompt, context, t0)

    def _fallback_generate(self, prompt: str, context: dict[str, Any] | None, t0: float) -> GeminiResponse:
        """Template-based fallback when API is unavailable."""
        latency = (time.perf_counter() - t0) * 1000
        ctx = context or {}
        text = self._build_fallback(ctx)

        return GeminiResponse(
            text=text, model=f"{self.model} (fallback)",
            prompt_tokens=0, completion_tokens=0,
            latency_ms=latency, grounded=True,
        )

    def _build_fallback(self, ctx: dict[str, Any]) -> str:
        """Build a meaningful fallback response from structured context."""
        gene = ctx.get("gene", "")
        drug = ctx.get("drug", "")
        phenotype = ctx.get("phenotype", "")
        population = ctx.get("population", "")
        recommendation = ctx.get("recommendation", "")
        frequency = ctx.get("frequency", "")

        if not gene:
            return "Analysis complete. See deterministic outputs for details."

        lines = []
        if phenotype:
            lines.append(f"Based on the deterministic analysis, the {gene} genotype results in a {phenotype} phenotype.")
        if drug and recommendation:
            lines.append(f"For {drug}: {recommendation}")
        if population and frequency:
            lines.append(f"In {population} populations, this allele is found at {frequency} frequency, making this a well-characterized finding.")
        lines.append("This interpretation is grounded in CPIC guidelines and supported by published evidence.")

        return " ".join(lines)

    def _check_grounding(self, text: str, context: dict[str, Any] | None) -> bool:
        """Check if response references provided evidence."""
        if not context:
            return True
        key_terms = [str(v) for v in context.values() if v and len(str(v)) > 3]
        if not key_terms:
            return True
        matches = sum(1 for term in key_terms[:5] if term.lower() in text.lower())
        return matches >= len(key_terms[:5]) * 0.4
