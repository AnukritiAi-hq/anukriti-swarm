"""Anukriti Swarm — Narrative Agent.

Synthesizes verified findings into human-readable research reports.
Operates in GENERATIVE mode for narrative synthesis, with DETERMINISTIC
components for citation assembly and confidence labeling.

Future responsibilities:
- Clinical narrative synthesis from structured findings
- Evidence summarization with source attribution
- Confidence communication (ESTABLISHED vs INFERRED labels)
- Structured report formatting (per-gene sections)
- Citation and reference assembly

Constraint: Only operates on VERIFIED data. Never generates unsupported claims.
"""

from __future__ import annotations

from agents.base import BaseAgent
from agents.models import AgentType, ExecutionMode, TaskStatus
from agents.state import SwarmState


class NarrativeAgent(BaseAgent):
    """Narrative synthesis agent — the final output layer.

    Transforms verified, structured pharmacogenomic findings into
    a human-readable research report. This is the only agent that
    produces user-facing text.

    Input: Verified findings from upstream agents (chromosome, pharmacogene,
    population, retrieval results — all post-verification).

    Output: Structured report with labeled confidence, citations, and
    explicit limitations.

    Safety: Only operates on verified data. Every claim in the narrative
    must trace back to a verified finding or cited source.
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.NARRATIVE

    @property
    def execution_mode(self) -> ExecutionMode:
        return ExecutionMode.GENERATIVE

    def execute(self, state: SwarmState) -> SwarmState:
        """Generate narrative report from verified findings.

        Current: Returns placeholder narrative structure.
        Future: Will use LLM to synthesize findings into readable report,
        with structured output enforcement and citation linking.
        """
        pharmacogene_results = state.get("pharmacogene_results", [])
        population_contexts = state.get("population_contexts", [])
        evidence = state.get("evidence", [])
        verification_results = state.get("verification_results", [])

        narrative = self._synthesize_report(
            pharmacogene_results, population_contexts, evidence
        )
        citations = self._assemble_citations(evidence)

        return {
            "narrative": narrative,
            "citations": citations,
            "current_stage": "complete",
            "status": TaskStatus.DONE,
        }  # type: ignore[return-value]

    def _synthesize_report(
        self,
        pharmacogene_results: list,
        population_contexts: list,
        evidence: list,
    ) -> str:
        """Synthesize findings into narrative report.

        Current: Returns placeholder text.
        Future: LLM-based synthesis with structured output schema,
        confidence labels, and mandatory source attribution.
        """
        return "[PLACEHOLDER] Pharmacogenomic analysis report pending implementation."

    def _assemble_citations(self, evidence: list) -> list[str]:
        """Assemble citations from retrieved evidence.

        Current: Returns empty list.
        Future: Extract PMIDs, guideline IDs, and database versions
        from evidence passages and format as citations.
        """
        return []
