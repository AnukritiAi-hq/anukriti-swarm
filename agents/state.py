"""Anukriti Swarm — Execution state models.

LangGraph-compatible state definitions that flow through the execution graph.
State is the central data structure passed between nodes in the DAG — each
agent reads from and writes to this shared state object.

Design: TypedDict-based state for LangGraph compatibility. Each field
represents a channel that agents can read/append to.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict

from agents.models import (
    AgentResult,
    PharmacogeneResult,
    PopulationContext,
    TaskStatus,
    VariantRecord,
)


class SwarmState(TypedDict, total=False):
    """Top-level execution state flowing through the LangGraph DAG.

    This is the shared state object that all agents read from and write to.
    LangGraph passes this between nodes, with each node returning updates
    to specific keys.

    Future: Will be extended with additional channels as new agent types
    are added to the swarm.
    """

    # --- Input ---
    query: str                              # Original user query
    sample_id: str                          # VCF sample identifier
    population_hint: str | None             # User-provided population context

    # --- VCF Ingestion ---
    variants: list[VariantRecord]           # Parsed variant records
    target_genes: list[str]                 # Genes identified for analysis
    target_chromosomes: list[str]           # Chromosomes with relevant variants

    # --- Agent Outputs ---
    chromosome_results: list[AgentResult]   # Per-chromosome analysis results
    pharmacogene_results: list[PharmacogeneResult]  # Per-gene findings
    population_contexts: list[PopulationContext]     # Population frequency data
    evidence: list[dict[str, Any]]          # Retrieved evidence passages
    verification_results: list[AgentResult] # Verification outcomes

    # --- Narrative ---
    narrative: str                          # Final synthesized report
    citations: list[str]                    # Assembled references

    # --- Execution Metadata ---
    correlation_id: str                     # Links all messages in this run
    current_stage: str                      # Current pipeline stage
    errors: list[str]                       # Accumulated error messages
    status: TaskStatus                      # Overall execution status


@dataclass
class DAGNode:
    """A single node in the execution DAG.

    Represents one agent task with its dependencies and current status.
    The orchestrator builds a graph of these nodes and executes them
    respecting dependency ordering.

    Future: Will support conditional edges (skip nodes based on upstream results)
    and dynamic node insertion (add agents based on intermediate findings).
    """

    node_id: str
    agent_type: str
    agent_id: str
    task_params: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: AgentResult | None = None
    timeout_seconds: int = 30
    retry_count: int = 0
    max_retries: int = 2


@dataclass
class ExecutionPlan:
    """Complete execution plan compiled by the orchestrator.

    Contains the full DAG of nodes to execute for a given query.
    The orchestrator compiles this from the query and VCF data,
    then executes nodes as their dependencies are satisfied.

    Future: Will support plan modification mid-execution (e.g., adding
    verification nodes dynamically when generative output is detected).
    """

    plan_id: str
    correlation_id: str
    nodes: list[DAGNode] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING

    def ready_nodes(self) -> list[DAGNode]:
        """Return nodes whose dependencies are all satisfied."""
        done_ids = {n.node_id for n in self.nodes if n.status == TaskStatus.DONE}
        return [
            n
            for n in self.nodes
            if n.status == TaskStatus.PENDING and all(d in done_ids for d in n.dependencies)
        ]
