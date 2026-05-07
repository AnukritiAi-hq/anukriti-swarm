"""Anukriti Swarm — Retrieval Agent.

Retrieves supporting evidence for pharmacogenomic findings.
Uses mock evidence data (future: MCP Retrieval server with Qdrant).
"""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from agents.models import AgentType, ExecutionMode
from agents.state import SwarmState
from datasets.mock_data import MOCK_EVIDENCE


class RetrievalAgent(BaseAgent):
    """Evidence retrieval agent.

    Searches for supporting literature and guideline passages
    relevant to the genes identified in the analysis.
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.RETRIEVAL

    @property
    def execution_mode(self) -> ExecutionMode:
        return ExecutionMode.DETERMINISTIC

    def execute(self, state: SwarmState) -> SwarmState:
        """Retrieve evidence for target genes from mock knowledge base."""
        target_genes = state.get("target_genes", [])
        evidence = [e for e in MOCK_EVIDENCE if e["gene"] in target_genes]
        return {"evidence": evidence}  # type: ignore[return-value]
