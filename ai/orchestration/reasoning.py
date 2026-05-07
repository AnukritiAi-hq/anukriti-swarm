"""AI-assisted orchestration reasoning summaries.

Generates human-readable summaries of what the swarm did and why,
plus comparative analysis across populations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ai.gemini.client import GeminiClient
from ai.prompts.templates import orchestration_summary, population_comparison


@dataclass
class OrchestrationSummary:
    """AI-generated summary of swarm orchestration."""

    summary: str
    agents_involved: list[str]
    reasoning_chain: str
    grounded: bool
    model: str
    latency_ms: float
    origin: str = "generative"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PopulationComparison:
    """AI-generated comparative analysis across populations."""

    comparison: str
    populations: list[str]
    key_differences: list[str]
    equity_note: str
    grounded: bool
    origin: str = "generative"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class OrchestrationReasoner:
    """Generates orchestration summaries and comparative analyses."""

    def __init__(self, client: GeminiClient | None = None) -> None:
        self.client = client or GeminiClient()

    def summarize_execution(self, state: dict[str, Any]) -> OrchestrationSummary:
        """Summarize what the swarm did for a given execution."""
        ctx = {
            "gene": state.get("gene", ""),
            "drug": state.get("drug", ""),
            "population": state.get("population", ""),
            "phenotype": state.get("pharmacogene_result", {}).get("phenotype", ""),
            "risk": state.get("pharmacogene_result", {}).get("risk", ""),
            "verification": state.get("verification", {}).get("verdict", ""),
            "confidence": state.get("verification", {}).get("confidence", ""),
            "agents": state.get("agents_dispatched", []),
            "stages": ["intake", "orchestration", "population", "pharmacogene", "retrieval", "verification", "narrative"],
        }

        prompt = orchestration_summary(ctx)
        response = self.client.generate(prompt, context=ctx)

        return OrchestrationSummary(
            summary=response.text,
            agents_involved=ctx["agents"],
            reasoning_chain=f"{ctx['gene']} {ctx.get('phenotype', '')} → {ctx.get('risk', '')} → verified ({ctx.get('verification', '')})",
            grounded=response.grounded,
            model=response.model,
            latency_ms=response.latency_ms,
        )

    def compare_populations(
        self, gene: str, drug: str, population_results: dict[str, dict[str, Any]]
    ) -> PopulationComparison:
        """Generate comparative analysis across populations."""
        pop_data_lines = []
        key_diffs = []
        for pop, data in population_results.items():
            freq = data.get("frequency", "?")
            phenotype = data.get("phenotype", "?")
            risk = data.get("risk", "?")
            pop_data_lines.append(f"{pop}: freq={freq}, phenotype={phenotype}, risk={risk}")
            key_diffs.append(f"{pop}: {phenotype} ({risk})")

        ctx = {
            "gene": gene, "drug": drug,
            "population_data": "\n".join(pop_data_lines),
            "populations": list(population_results.keys()),
        }

        prompt = population_comparison(ctx)
        response = self.client.generate(prompt, context=ctx)

        # Extract equity note from context
        populations = list(population_results.keys())
        risks = [d.get("risk", "") for d in population_results.values()]
        equity_note = "Population-specific risk variation detected." if len(set(risks)) > 1 else "Consistent risk across populations."

        return PopulationComparison(
            comparison=response.text,
            populations=populations,
            key_differences=key_diffs,
            equity_note=equity_note,
            grounded=response.grounded,
        )
