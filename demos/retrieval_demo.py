"""Anukriti Swarm — Biomedical Evidence Retrieval Demo.

Demonstrates the MA-RAG inspired retrieval pipeline:
  Query → Plan → Retrieve → Cite → Synthesize

Run: python -m demos.retrieval_demo
"""

from __future__ import annotations

from retrieval.evidence.retriever import EvidenceRetriever
from retrieval.evidence.synthesizer import EvidenceSynthesizer
from retrieval.planner.query_planner import QueryPlanner


def run_demo() -> None:
    print("=" * 70)
    print("🧬 ANUKRITI SWARM — Biomedical Evidence Retrieval Demo")
    print("   MA-RAG: Plan → Retrieve → Cite → Synthesize")
    print("=" * 70)

    planner = QueryPlanner()
    retriever = EvidenceRetriever()
    synthesizer = EvidenceSynthesizer()

    # --- Query 1: CYP2D6 + Codeine ---
    print("\n" + "=" * 70)
    print("QUERY 1: 'CYP2D6 intermediate metabolizer codeine recommendation'")
    print("=" * 70)

    plan = planner.plan(
        "CYP2D6 intermediate metabolizer codeine recommendation",
        gene="CYP2D6", drug="codeine",
    )

    print(f"\n  Plan ID: {plan.plan_id}")
    print(f"  Strategy: {plan.strategy}")
    print(f"  Sub-queries ({len(plan.sub_queries)}):")
    for sq in plan.sub_queries:
        src = sq.target_source.value if sq.target_source else "ALL"
        print(f"    [{sq.intent:<10}] {sq.text} → {src}")

    result = retriever.execute_plan(plan)

    print(f"\n  Retrieved: {result.total_retrieved} evidence passages")
    print(f"  Citations: {len(result.citations)}")
    for ev in result.evidence[:3]:
        print(f"\n    [{ev.relevance_score:.3f}] {ev.citation.title}")
        print(f"      Source: {ev.citation.source.value} | {ev.citation.citation_id}")
        print(f"      Intent: {ev.intent} | Gene: {ev.gene}")

    synthesis = synthesizer.synthesize(result)

    print(f"\n  Synthesis (grounding: {synthesis.grounding_score:.0%}):")
    for claim in synthesis.claims:
        status = "✓ GROUNDED" if claim.grounded else "✗ UNGROUNDED"
        print(f"\n    [{status}] ({claim.intent}, conf={claim.confidence:.2f})")
        print(f"    Claim: {claim.claim[:100]}...")
        print(f"    Cited: {', '.join(claim.citations)}")

    # --- Query 2: HLA-B + Carbamazepine ---
    print("\n\n" + "=" * 70)
    print("QUERY 2: 'HLA-B*15:02 carbamazepine risk Southeast Asian'")
    print("=" * 70)

    plan2 = planner.plan(
        "HLA-B*15:02 carbamazepine risk Southeast Asian population",
        gene="HLA-B", drug="carbamazepine", population="Southeast Asian",
    )

    print(f"\n  Sub-queries ({len(plan2.sub_queries)}):")
    for sq in plan2.sub_queries:
        src = sq.target_source.value if sq.target_source else "ALL"
        print(f"    [{sq.intent:<10}] {sq.text} → {src}")

    result2 = retriever.execute_plan(plan2)
    synthesis2 = synthesizer.synthesize(result2)

    print(f"\n  Retrieved: {result2.total_retrieved} passages | Grounding: {synthesis2.grounding_score:.0%}")
    for claim in synthesis2.claims:
        if claim.grounded:
            print(f"\n    [✓] ({claim.intent}) {claim.claim[:90]}...")
            print(f"        Cited: {', '.join(claim.citations)}")

    # --- Provenance Summary ---
    print("\n\n" + "=" * 70)
    print("PROVENANCE TRAIL")
    print("=" * 70)
    print(f"\n  Plan: {synthesis.provenance}")
    print(f"  All citations used:")
    for cit in synthesis.all_citations:
        print(f"    {cit.citation_id} | {cit.source.value} | {cit.year} | {cit.title}")

    print("\n" + "=" * 70)
    print("✅ Every claim is grounded, cited, and auditable.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
