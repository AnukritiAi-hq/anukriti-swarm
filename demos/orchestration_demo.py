"""Anukriti Swarm — Orchestration Demo.

Demonstrates the full pharmacogenomic analysis pipeline:
  VCF variants → orchestration → chromosome analysis → population context
  → evidence retrieval → verification → narrative report

Run: python -m demos.orchestration_demo
"""

from __future__ import annotations

import uuid

from agents.chromosome.chr10 import Chromosome10Agent
from agents.chromosome.chr22 import Chromosome22Agent
from agents.chromosome.chr6 import Chromosome6Agent
from agents.logging import ExecutionTrace, setup_logging
from agents.narrative import NarrativeAgent
from agents.orchestrator import OrchestratorAgent
from agents.population.sas import SASAgent
from agents.retrieval import RetrievalAgent
from agents.state import SwarmState
from agents.verification import VerificationAgent
from datasets.mock_data import ALL_MOCK_VARIANTS
from workflows.graph import StateGraph


def build_demo_graph() -> StateGraph:
    """Build the full orchestration graph for the demo."""
    graph = StateGraph()

    # Instantiate agents
    orchestrator = OrchestratorAgent()
    chr6 = Chromosome6Agent()
    chr10 = Chromosome10Agent()
    chr22 = Chromosome22Agent()
    population = SASAgent()
    retrieval = RetrievalAgent()
    verification = VerificationAgent()
    narrative = NarrativeAgent()

    # Add nodes
    graph.add_node("orchestrator", orchestrator)
    graph.add_node("chr6", chr6, parallel_group="chromosome")
    graph.add_node("chr10", chr10, parallel_group="chromosome")
    graph.add_node("chr22", chr22, parallel_group="chromosome")
    graph.add_node("population", population)
    graph.add_node("retrieval", retrieval)
    graph.add_node("verification", verification)
    graph.add_node("narrative", narrative)

    # Define edges (execution order)
    graph.add_edge("orchestrator", "chr6")
    graph.add_edge("orchestrator", "chr10")
    graph.add_edge("orchestrator", "chr22")
    graph.add_edge("chr6", "population")
    graph.add_edge("chr10", "population")
    graph.add_edge("chr22", "population")
    graph.add_edge("population", "retrieval")
    graph.add_edge("retrieval", "verification")
    graph.add_edge("verification", "narrative")

    graph.set_entry_point("orchestrator")
    return graph


def run_demo() -> None:
    """Execute the demo pipeline and print results."""
    setup_logging()

    print("=" * 70)
    print("🧬 ANUKRITI SWARM — Orchestration Demo")
    print("=" * 70)
    print()
    print("Input:")
    print(f"  Ancestry: South Asian (SAS)")
    print(f"  Drug context: codeine, clopidogrel")
    print(f"  Variants: {len(ALL_MOCK_VARIANTS)} pharmacogenomic variants")
    print()

    # Build initial state
    initial_state: SwarmState = {
        "query": "Analyze pharmacogenomic profile for South Asian patient",
        "sample_id": "DEMO_001",
        "population_hint": "SAS",
        "variants": ALL_MOCK_VARIANTS,
    }  # type: ignore[typeddict-item]

    # Build and run graph
    graph = build_demo_graph()
    trace = ExecutionTrace(correlation_id=uuid.uuid4().hex[:12])

    print("-" * 70)
    print("Executing pipeline...")
    print("-" * 70)
    print()

    result = graph.run(initial_state, trace)

    # Print execution trace
    print()
    print("-" * 70)
    print("Execution Trace:")
    print("-" * 70)
    print(trace.summary())

    # Print narrative report
    print()
    print("-" * 70)
    print("Generated Report:")
    print("-" * 70)
    print()
    print(result.get("narrative", "[No narrative generated]"))

    # Print verification summary
    print()
    print("-" * 70)
    print("Verification Summary:")
    print("-" * 70)
    for v in result.get("verification_results", []):
        gene = v.output.get("gene", "?")
        verdict = v.output.get("verdict", "?")
        passed = v.output.get("checks_passed", [])
        print(f"  {gene}: {verdict.upper()} ({len(passed)}/3 checks passed)")

    print()
    print("=" * 70)
    print("✅ Pipeline complete. All agents collaborated successfully.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
