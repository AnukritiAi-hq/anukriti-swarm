"""Anukriti Swarm — Base Orchestrator Agent (LangGraph node).

The ``OrchestratorAgent`` is the original, lightweight orchestrator used as
the first node in the LangGraph pipeline. It performs pure, deterministic
routing work:

- Assigns a correlation_id for tracing
- Extracts target genes from variant records
- Extracts target chromosomes for parallel analysis
- Sets pipeline stage metadata

This agent is the **deterministic skeleton** of the orchestration layer.
It is intentionally kept small and dependency-light so it can run inside
any pipeline without pulling in the generative Gemini stack.

For Gemini-powered high-level orchestration (query decomposition,
multi-agent coordination, comparative analysis) see:

- ``agents.orchestrator.gemini_orchestrator.GeminiOrchestrator``
- ``core.orchestrator`` (framework primitives)

Layering:
    agents.orchestrator.agent.OrchestratorAgent   ← low-level graph node
    agents.orchestrator.gemini_orchestrator       ← high-level framework
    core.orchestrator.*                           ← reusable primitives
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
