"""Anukriti Swarm — Agent Identity & Federation Demo.

Demonstrates the swarm as a federation of specialized genomic experts,
each with clear identity, capabilities, and routing metadata.

Run: python -m demos.agent_identity_demo
"""

from __future__ import annotations

from agents.profiles.identity import AgentDomain
from agents.registry.registry import AgentRegistry


def run_demo() -> None:
    print("=" * 70)
    print("🧬 ANUKRITI SWARM — Agent Identity & Federation")
    print("   A federation of specialized genomic experts.")
    print("=" * 70)

    # Initialize registry
    registry = AgentRegistry()
    registry.register_all()

    # Federation overview
    print(f"\n{registry.federation_summary()}")

    # --- Query routing demo ---
    print("=" * 70)
    print("ROUTING DEMO: Who handles 'CYP2C19 + clopidogrel + SAS'?")
    print("=" * 70)

    matches = registry.find_for_query(gene="CYP2C19", drug="clopidogrel", population="SAS")
    print(f"\n  Matched {len(matches)} agents (priority order):\n")
    for a in matches:
        print(f"    [{a.priority}] {a.name}")
        print(f"        Domain: {a.domain.value} | Mode: {a.reasoning_mode.value}")
        print(f"        Capabilities: {', '.join(a.capabilities[:3])}")
        print()

    # --- Capability search ---
    print("─" * 70)
    print("CAPABILITY: Who can do 'hallucination_detection'?")
    print("─" * 70)

    detectors = registry.find_by_capability("hallucination_detection")
    for a in detectors:
        print(f"  → {a.name} ({a.agent_id})")

    # --- Safety-critical agents ---
    print(f"\n{'─' * 70}")
    print("TAG: Safety-critical agents")
    print("─" * 70)

    safety = registry.find_by_tag("safety")
    for a in safety:
        print(f"  🛡️  {a.name} (priority={a.priority}, escalation_threshold={a.confidence_profile.escalation_threshold})")

    # --- Individual profile introspection ---
    print(f"\n{'─' * 70}")
    print("INTROSPECTION: CYP2D6 Expert Profile")
    print("─" * 70)

    cyp2d6 = registry.get("pharmacogene_cyp2d6")
    if cyp2d6:
        print(f"\n{cyp2d6.summary()}")
        print(f"\n  Routing keywords: {cyp2d6.routing_keywords}")
        print(f"  Escalation threshold: {cyp2d6.confidence_profile.escalation_threshold}")
        print(f"  Version: {cyp2d6.version}")
        print(f"  Tags: {cyp2d6.tags}")

    # --- Domain breakdown ---
    print(f"\n{'─' * 70}")
    print("DOMAIN BREAKDOWN")
    print("─" * 70)

    for domain in [AgentDomain.POPULATION_GENOMICS, AgentDomain.PHARMACOGENOMICS]:
        agents = registry.find_by_domain(domain)
        print(f"\n  {domain.value} ({len(agents)} agents):")
        for a in agents:
            genes = ", ".join(a.supported_genes[:3]) or "all"
            print(f"    • {a.name} → genes: {genes}")

    print(f"\n{'=' * 70}")
    print("✅ Federation ready. 9 specialized agents. Full introspection.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
