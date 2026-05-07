"""Anukriti Swarm — Communication Layer Demo.

Demonstrates inter-agent messaging patterns:
1. Orchestrator → Population Agent (task delegation)
2. Population Agent → Retrieval Agent (evidence request)
3. Verification escalation flow (broadcast)

Run: python -m demos.communication_demo
"""

from __future__ import annotations

from communication.bus import MessageBus
from communication.context import ExecutionContext
from communication.messages import MessageEnvelope, MessageType
from communication.patterns import AgentCommunicator
from events.emitter import EventEmitter, console_listener
from events.types import EventCategory, EventSeverity, SwarmEvent


def mock_population_handler(msg: MessageEnvelope) -> MessageEnvelope | None:
    """Mock population agent: receives task, returns frequency data."""
    gene = msg.payload.get("parameters", {}).get("gene", "unknown")
    return msg.create_reply(
        source_agent="population_sas",
        message_type=MessageType.TASK_RESULT,
        payload={
            "gene": gene,
            "population": "SAS",
            "frequency": 0.09,
            "source": "gnomAD v4.0",
        },
    )


def mock_retrieval_handler(msg: MessageEnvelope) -> MessageEnvelope | None:
    """Mock retrieval agent: receives evidence request, returns passages."""
    gene = msg.payload.get("gene", "unknown")
    return msg.create_reply(
        source_agent="retrieval_main",
        message_type=MessageType.EVIDENCE_RESPONSE,
        payload={
            "gene": gene,
            "passages": [
                {"source": "PMID:32722396", "text": "CPIC guideline for CYP2D6..."},
            ],
            "count": 1,
        },
    )


def run_demo() -> None:
    """Execute the communication demo."""
    print("=" * 70)
    print("🧬 ANUKRITI SWARM — Communication Layer Demo")
    print("=" * 70)

    # Setup
    bus = MessageBus()
    emitter = EventEmitter()
    emitter.add_listener(lambda e: print(f"  [EVENT] {e.severity.value:>5} | {e.agent_id:<20} | {e.action}"))

    # Register mock agents
    bus.register("population_sas", mock_population_handler)
    bus.register("retrieval_main", mock_retrieval_handler)

    # Create execution context
    ctx = ExecutionContext(
        current_agent="orchestrator_01",
        stage="orchestration",
        population="SAS",
        drug_context=["codeine"],
        target_genes=["CYP2D6"],
    )

    # --- Demo 1: Orchestrator → Population Agent ---
    print("\n" + "-" * 70)
    print("1. Orchestrator → Population Agent (task delegation)")
    print("-" * 70)

    orchestrator_comm = AgentCommunicator("orchestrator_01", bus, ctx)

    with emitter.trace_execution("orchestrator_01", ctx.correlation_id, "delegate_to_population"):
        reply = orchestrator_comm.delegate_task(
            target_agent="population_sas",
            task_type="frequency_lookup",
            parameters={"gene": "CYP2D6", "population": "SAS"},
        )

    if reply:
        print(f"\n  Reply from: {reply.source_agent}")
        print(f"  Payload: {reply.payload}")
        print(f"  Correlation: {reply.correlation_id[:12]}...")
        print(f"  Causation chain: {reply.causation_id[:12]}... → {reply.message_id[:12]}...")

    # --- Demo 2: Population Agent → Retrieval Agent ---
    print("\n" + "-" * 70)
    print("2. Population Agent → Retrieval Agent (evidence request)")
    print("-" * 70)

    pop_ctx = ctx.child("population_sas", "population_analysis")
    pop_comm = AgentCommunicator("population_sas", bus, pop_ctx)

    with emitter.trace_execution("population_sas", ctx.correlation_id, "request_evidence"):
        evidence_reply = pop_comm.request_evidence(
            target_agent="retrieval_main",
            gene="CYP2D6",
            query="CYP2D6 allele frequency South Asian population",
        )

    if evidence_reply:
        print(f"\n  Reply from: {evidence_reply.source_agent}")
        print(f"  Passages: {evidence_reply.payload.get('count')} found")
        print(f"  Context depth: {pop_ctx.depth} (parent: {pop_ctx.parent_agents})")

    # --- Demo 3: Verification Escalation ---
    print("\n" + "-" * 70)
    print("3. Verification Agent → Escalation (broadcast)")
    print("-" * 70)

    verify_ctx = ctx.child("verification_01", "verification")
    verify_comm = AgentCommunicator("verification_01", bus, verify_ctx)

    with emitter.trace_execution("verification_01", ctx.correlation_id, "escalation"):
        verify_comm.escalate(
            reason="Confidence below threshold (0.45 < 0.70) for CYP2D6 novel interaction",
            severity="high",
            context={"gene": "CYP2D6", "confidence": 0.45, "threshold": 0.70},
        )

    # --- Summary ---
    print("\n" + "-" * 70)
    print("Message Bus History:")
    print("-" * 70)
    for msg in bus.get_history():
        direction = f"{msg.source_agent} → {msg.target_agent or 'BROADCAST'}"
        print(f"  [{msg.message_type.value:<20}] {direction}")

    print(f"\n  Dead letters: {len(bus.dead_letters)}")

    print("\n" + "-" * 70)
    print("Event Trace:")
    print("-" * 70)
    print(emitter.summary(ctx.correlation_id))

    print("\n" + "=" * 70)
    print("✅ Communication layer demo complete.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
