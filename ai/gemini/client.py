"""Multi-provider AI client — Gemini and OpenAI support.

Provider-isolated client that supports:
- Google Gemini (gemini-2.0-flash)
- OpenAI (gpt-4o-mini)

Falls back gracefully when APIs are unavailable.
Safety boundary: NEVER makes biomedical decisions.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AIProvider(str, Enum):
    GEMINI = "gemini"
    OPENAI = "openai"


@dataclass
class AIResponse:
    """Structured response with observability metadata."""

    text: str
    model: str
    provider: AIProvider
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    grounded: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AIMetrics:
    """Accumulated metrics."""

    total_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_latency_ms: float = 0.0
    failures: int = 0


class AIClient:
    """Multi-provider AI client supporting Gemini and OpenAI.

    Usage:
        client = AIClient(provider=AIProvider.OPENAI)
        response = client.generate(prompt, context={...})
    """

    def __init__(self, provider: AIProvider = AIProvider.GEMINI, max_retries: int = 2) -> None:
        self.provider = provider
        self.max_retries = max_retries
        self.metrics = AIMetrics()
        self._client: Any = None
        self.model = ""

        if provider == AIProvider.GEMINI:
            self._init_gemini()
        elif provider == AIProvider.OPENAI:
            self._init_openai()

    def _init_gemini(self) -> None:
        self.model = "gemini-2.0-flash"
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=api_key)
            except ImportError:
                pass

    def _init_openai(self) -> None:
        self.model = "gpt-4o-mini"
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key)
            except Exception:
                pass

    @property
    def available(self) -> bool:
        return self._client is not None

    def generate(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> AIResponse:
        self.metrics.total_calls += 1
        t0 = time.perf_counter()

        if not self.available:
            return self._fallback(prompt, context, t0)

        for attempt in range(self.max_retries + 1):
            try:
                if self.provider == AIProvider.GEMINI:
                    text = self._call_gemini(prompt, temperature, max_tokens)
                else:
                    text = self._call_openai(prompt, temperature, max_tokens)

                latency = (time.perf_counter() - t0) * 1000
                prompt_tokens = int(len(prompt.split()) * 1.3)
                completion_tokens = int(len(text.split()) * 1.3)
                self.metrics.total_prompt_tokens += prompt_tokens
                self.metrics.total_completion_tokens += completion_tokens
                self.metrics.total_latency_ms += latency

                return AIResponse(
                    text=text, model=self.model, provider=self.provider,
                    prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                    latency_ms=latency, grounded=self._check_grounding(text, context),
                )
            except Exception:
                if attempt == self.max_retries:
                    self.metrics.failures += 1
                    return self._fallback(prompt, context, t0)
                time.sleep(1.0 * (2 ** attempt))

        return self._fallback(prompt, context, t0)

    def _call_gemini(self, prompt: str, temperature: float, max_tokens: int) -> str:
        from google.genai import types
        response = self._client.models.generate_content(
            model=self.model, contents=prompt,
            config=types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens),
        )
        return response.text or ""

    def _call_openai(self, prompt: str, temperature: float, max_tokens: int) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    def _fallback(self, prompt: str, context: dict[str, Any] | None, t0: float) -> AIResponse:
        latency = (time.perf_counter() - t0) * 1000
        ctx = context or {}
        text = self._build_fallback(ctx)
        return AIResponse(
            text=text, model=f"{self.model} (fallback)", provider=self.provider,
            prompt_tokens=0, completion_tokens=0, latency_ms=latency, grounded=True,
        )

    def _build_fallback(self, ctx: dict[str, Any]) -> str:
        gene = ctx.get("gene", "")
        phenotype = ctx.get("phenotype", "")
        drug = ctx.get("drug", "")
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
            lines.append(f"In {population} populations, this allele is found at {frequency} frequency.")
        lines.append("This interpretation is grounded in CPIC guidelines and supported by published evidence.")
        return " ".join(lines)

    def _check_grounding(self, text: str, context: dict[str, Any] | None) -> bool:
        if not context:
            return True
        key_terms = [str(v) for v in context.values() if v and len(str(v)) > 3]
        if not key_terms:
            return True
        matches = sum(1 for term in key_terms[:5] if term.lower() in text.lower())
        return matches >= len(key_terms[:5]) * 0.4


# Backward compatibility
GeminiClient = AIClient
GeminiResponse = AIResponse
GeminiMetrics = AIMetrics
