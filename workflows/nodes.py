"""Pipeline node functions for each execution stage.

Each node is a pure function: state → partial_updates.
Nodes integrate the existing agent/reasoning/retrieval/verification layers.
All outputs carry provenance and are deterministic.
"""

from __future__ import annotations

from typing import Any

from agents.pharmacogene.cyp2c19 import CYP2C19Agent
from agents.pharmacogene.cyp2d6 import CYP2D6Agent
from guidelines.cpic import lookup_recommendation
from population.agents import SASPopulationAgent, AFRPopulationAgent, EURPopulationAgent
from retrieval.evidence.retriever import EvidenceRetriever
from retrieval.planner.query_planner import QueryPlanner
from retrieval.evidence.synthesizer import EvidenceSynthesizer
from verification.engine import VerificationEngine

# State type alias
State = dict[str, Any]

# Pre-instantiate agents (stateless, reusable)
_POPULATION_AGENTS = {"SAS": SASPopulationAgent(), "AFR": AFRPopulationAgent(), "EUR": EURPopulationAgent()}
_PHARMACOGENE_AGENTS = {"CYP2C19": CYP2C19Agent(), "CYP2D6": CYP2D6Agent()}
_PLANNER = QueryPlanner()
_RETRIEVER = EvidenceRetriever()
_SYNTHESIZER = EvidenceSynthesizer()
_VERIFIER = VerificationEngine()


def node_intake(state: State) -> State:
    """Stage 1: Validate and normalize input."""
    gene = state.get("gene", "")
    drug = state.get("drug", "")
    population = state.get("population", "")
    allele1 = state.get("allele1", "*1")
    allele2 = state.get("allele2", "*1")

    return {
        "stage": "intake",
        "gene": gene,
        "drug": drug,
        "population": population,
        "allele1": allele1,
        "allele2": allele2,
        "diplotype": f"{allele1}/{allele2}",
        "input_valid": bool(gene and drug and population),
    }


def node_orchestration(state: State) -> State:
    """Stage 2: Plan execution and route to agents."""
    gene = state["gene"]
    population = state["population"]

    agents_needed = []
    if gene in _PHARMACOGENE_AGENTS:
        agents_needed.append(f"pharmacogene_{gene.lower()}")
    if population in _POPULATION_AGENTS:
        agents_needed.append(f"population_{population.lower()}")
    agents_needed.extend(["retrieval", "verification", "narrative"])

    return {
        "stage": "orchestration",
        "agents_dispatched": agents_needed,
        "execution_plan": f"analyze {gene} {state['diplotype']} in {population} for {state['drug']}",
    }


def node_population(state: State) -> State:
    """Stage 3: Population-aware reasoning."""
    population = state["population"]
    gene = state["gene"]
    allele = state.get("allele2", "*1")  # Analyze the non-reference allele

    agent = _POPULATION_AGENTS.get(population)
    if not agent:
        return {"stage": "population", "population_result": None, "_stage_warning": True}

    result = agent.reason(gene, allele)

    return {
        "stage": "population",
        "population_result": {
            "population": result.population,
            "frequency": result.frequency.frequency,
            "rarity": result.risk_context.rarity_class,
            "clinical_note": result.risk_context.clinical_note,
            "confidence": result.confidence,
            "source": f"{result.frequency.source} {result.frequency.version}",
            "sample_n": result.frequency.sample_n,
        },
        "population_prevalence": [
            {"phenotype": p.phenotype, "prevalence": p.prevalence}
            for p in result.prevalence_estimates
        ],
    }


def node_pharmacogene(state: State) -> State:
    """Stage 4: Deterministic pharmacogene reasoning."""
    gene = state["gene"]
    allele1 = state["allele1"]
    allele2 = state["allele2"]

    agent = _PHARMACOGENE_AGENTS.get(gene)
    if not agent:
        return {"stage": "pharmacogene", "pharmacogene_result": None, "_stage_warning": True}

    analysis = agent.analyze_diplotype(allele1, allele2)

    return {
        "stage": "pharmacogene",
        "pharmacogene_result": {
            "gene": analysis.gene,
            "diplotype": analysis.diplotype,
            "activity_score": analysis.phenotype_inference.activity_score,
            "phenotype": analysis.phenotype_inference.phenotype,
            "risk": analysis.risk_classification,
            "confidence": analysis.confidence,
            "origin": analysis.origin,
            "provenance": analysis.provenance,
        },
        "recommendations": [
            {
                "drug": r.drug,
                "recommendation": r.recommendation,
                "strength": r.strength,
                "guideline_id": r.guideline_id,
                "pmid": r.pmid,
            }
            for r in analysis.recommendations
        ],
    }


def node_retrieval(state: State) -> State:
    """Stage 5: Evidence retrieval with MA-RAG pipeline."""
    gene = state["gene"]
    drug = state["drug"]
    population = state["population"]

    plan = _PLANNER.plan(
        f"{gene} {drug} {population} pharmacogenomics",
        gene=gene, drug=drug, population=population,
    )
    result = _RETRIEVER.execute_plan(plan)
    synthesis = _SYNTHESIZER.synthesize(result)

    return {
        "stage": "retrieval",
        "evidence_claims": [
            {"claim": c.claim[:200], "citations": c.citations, "grounded": c.grounded, "confidence": c.confidence}
            for c in synthesis.claims
        ],
        "citations": [c.citation_id for c in result.citations],
        "grounding_score": synthesis.grounding_score,
        "retrieval_count": result.total_retrieved,
    }


def node_verification(state: State) -> State:
    """Stage 6: Verify all outputs before narrative."""
    pgx = state.get("pharmacogene_result", {})
    pop = state.get("population_result", {})
    claims = state.get("evidence_claims", [])
    recs = state.get("recommendations", [])

    output = {
        "agent_id": f"pharmacogene_{pgx.get('gene', '').lower()}",
        "gene": pgx.get("gene", ""),
        "drug": state.get("drug", ""),
        "origin": pgx.get("origin", "deterministic"),
        "confidence": pgx.get("confidence", 1.0),
        "source": pgx.get("provenance", {}).get("guideline_source", ""),
        "population": pop.get("population", ""),
        "sample_n": pop.get("sample_n"),
        "frequency": pop.get("frequency"),
    }

    report = _VERIFIER.verify(
        output, claims=claims, recommendations=recs,
        stage_confidences={
            "phenotype": pgx.get("confidence", 1.0),
            "population": pop.get("confidence", 0.9),
            "evidence": state.get("grounding_score", 0.8),
        },
    )

    return {
        "stage": "verification",
        "verification": {
            "verdict": report.overall_verdict.value,
            "confidence": report.confidence.value if report.confidence else 0.0,
            "confidence_level": report.confidence.level.value if report.confidence else "unknown",
            "escalation_tier": report.escalation.tier.value if report.escalation else "unknown",
            "action": report.escalation.recommended_action if report.escalation else "",
            "checks": [{"name": c.check_name, "verdict": c.verdict.value, "reason": c.reason} for c in report.checks],
        },
    }


def node_narrative(state: State) -> State:
    """Stage 7: Generate evidence-backed narrative."""
    pgx = state.get("pharmacogene_result", {})
    pop = state.get("population_result", {})
    recs = state.get("recommendations", [])
    citations = state.get("citations", [])
    verification = state.get("verification", {})

    lines = [
        "# Pharmacogenomic Analysis Report",
        "",
        "> ⚠️ Research only — not for clinical decision-making.",
        "",
        "## Patient Context",
        f"- **Gene:** {pgx.get('gene', 'N/A')}",
        f"- **Diplotype:** {pgx.get('diplotype', 'N/A')} [ESTABLISHED]",
        f"- **Drug:** {state.get('drug', 'N/A')}",
        f"- **Population:** {pop.get('population', 'N/A')}",
        "",
        "## Phenotype Assessment",
        f"- **Phenotype:** {pgx.get('phenotype', 'N/A')} [ESTABLISHED]",
        f"- **Activity Score:** {pgx.get('activity_score', 'N/A')}",
        f"- **Risk Classification:** {pgx.get('risk', 'N/A')}",
        f"- **Confidence:** {pgx.get('confidence', 'N/A')}",
        "",
        "## Population Context",
        f"- **Allele frequency:** {pop.get('frequency', 'N/A')}",
        f"- **Rarity in population:** {pop.get('rarity', 'N/A')}",
        f"- **Note:** {pop.get('clinical_note', 'N/A')}",
        "",
        "## Recommendations",
    ]
    for r in recs:
        lines.append(f"- [{r['strength'].upper()}] **{r['drug']}**: {r['recommendation']}")
        lines.append(f"  - Source: {r['guideline_id']} ({r['pmid']})")
    lines.extend([
        "",
        "## Verification",
        f"- **Verdict:** {verification.get('verdict', 'N/A')}",
        f"- **Confidence:** {verification.get('confidence', 'N/A'):.3f} ({verification.get('confidence_level', '')})",
        f"- **Escalation:** {verification.get('escalation_tier', 'N/A')}",
        "",
        "## References",
    ])
    for cit in citations:
        lines.append(f"- {cit}")
    lines.extend(["", "---", "*Generated by Anukriti Swarm. Deterministic reasoning. Full provenance.*"])

    return {"stage": "complete", "narrative": "\n".join(lines)}
