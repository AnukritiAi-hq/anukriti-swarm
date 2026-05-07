"""Anukriti Swarm — Narrative Agent.

Synthesizes verified findings into a structured pharmacogenomic report.
Uses template-based generation (future: LLM synthesis with grounding).
"""

from __future__ import annotations

from agents.base import BaseAgent
from agents.models import AgentType, ExecutionMode, PharmacogeneResult, PopulationContext, TaskStatus
from agents.state import SwarmState


class NarrativeAgent(BaseAgent):
    """Narrative agent — generates human-readable report from verified findings.

    Template-based synthesis that formats pharmacogene results, population
    context, and evidence into a structured research report.
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.NARRATIVE

    @property
    def execution_mode(self) -> ExecutionMode:
        return ExecutionMode.GENERATIVE

    def execute(self, state: SwarmState) -> SwarmState:
        """Generate narrative report from verified findings."""
        pharmacogene_results = state.get("pharmacogene_results", [])
        population_contexts = state.get("population_contexts", [])
        evidence = state.get("evidence", [])

        narrative = self._build_report(pharmacogene_results, population_contexts, evidence)
        citations = [e["source"] for e in evidence]

        return {
            "narrative": narrative,
            "citations": citations,
            "current_stage": "complete",
            "status": TaskStatus.DONE,
        }  # type: ignore[return-value]

    def _build_report(
        self,
        results: list[PharmacogeneResult],
        contexts: list[PopulationContext],
        evidence: list[dict],
    ) -> str:
        """Build structured report from findings."""
        sections = ["# Pharmacogenomic Analysis Report", ""]
        sections.append("> ⚠️ Research only — not for clinical decision-making.")
        sections.append("")

        # Per-gene findings
        sections.append("## Findings")
        sections.append("")
        for pgx in results:
            sections.append(f"### {pgx.gene}")
            sections.append(f"- **Diplotype:** {pgx.diplotype} [ESTABLISHED]")
            sections.append(f"- **Phenotype:** {pgx.phenotype} [ESTABLISHED]")
            sections.append(f"- **Drugs affected:** {', '.join(pgx.drugs_affected)}")
            sections.append(f"- **Source:** {pgx.guideline_source}")
            sections.append("")

        # Population context
        if contexts:
            sections.append("## Population Context")
            sections.append("")
            for ctx in contexts:
                freq = f"{ctx.allele_frequency:.2%}" if ctx.allele_frequency else "unknown"
                sections.append(
                    f"- {ctx.population}: allele frequency {freq} ({ctx.frequency_source})"
                )
            sections.append("")

        # Evidence
        if evidence:
            sections.append("## Supporting Evidence")
            sections.append("")
            for e in evidence:
                sections.append(f"- [{e['source']}] {e['title']}")
                sections.append(f"  > {e['passage']}")
                sections.append("")

        # Limitations
        sections.append("## Limitations")
        sections.append("")
        sections.append("- Based on detected variants only; undetected variants may alter results")
        sections.append("- Population frequencies are reference values, individual may vary")
        sections.append("- This is a research output, not clinical guidance")

        return "\n".join(sections)
