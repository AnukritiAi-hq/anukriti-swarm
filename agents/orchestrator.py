"""Anukriti Swarm — Orchestrator Agent.

The central coordinator that decomposes queries, identifies target genes
and chromosomes from variants, and prepares state for downstream agents.

In the LangGraph pipeline, this is the first node: it reads raw input
(variants, population, drug) and populates routing metadata for the DAG.
"""

from __future__ import annotations

import uuid

from agents.base import BaseAgent
from agents.models import AgentType, ExecutionMode, TaskStatus, VariantRecord
from agents.state import SwarmState


class OrchestratorAgent(BaseAgent):
    """Central orchestrator — first node in the execution graph.

    Responsibilities:
    - Assign correlation_id for tracing
    - Extract target genes from variant records
    - Identify target chromosomes for parallel analysis
    - Set pipeline stage metadata
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.ORCHESTRATOR

    @property
    def execution_mode(self) -> ExecutionMode:
        return ExecutionMode.HYBRID

    def execute(self, state: SwarmState) -> SwarmState:
        """Analyze input and prepare routing metadata."""
        variants = state.get("variants", [])
        correlation_id = state.get("correlation_id") or uuid.uuid4().hex

        target_genes = self._extract_genes(variants)
        target_chromosomes = self._extract_chromosomes(variants)

        return {
            "correlation_id": correlation_id,
            "target_genes": target_genes,
            "target_chromosomes": target_chromosomes,
            "current_stage": "orchestration",
            "status": TaskStatus.RUNNING,
            "errors": [],
        }  # type: ignore[return-value]

    def _extract_genes(self, variants: list[VariantRecord]) -> list[str]:
        """Extract unique gene names from variants."""
        return list({v.gene for v in variants if v.gene})

    def _extract_chromosomes(self, variants: list[VariantRecord]) -> list[str]:
        """Extract unique chromosomes from variants."""
        return list({v.chromosome for v in variants})
