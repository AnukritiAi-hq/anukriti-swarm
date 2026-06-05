"""Google ADK-compatible agent wrappers.

Wraps Anukriti Swarm's existing agents as Google ADK-compatible
tool functions that can be invoked by a Gemini-powered orchestrator.

ADK pattern: agents expose tools → orchestrator invokes tools → results flow back.
Deterministic core remains authoritative — ADK provides the coordination layer.
"""

from __future__ import annotations

import os
from typing import Any

from agents.pharmacogene.cyp2c19 import CYP2C19Agent
from agents.pharmacogene.cyp2d6 import CYP2D6Agent
from agents.pharmacogene.hla_b import HLABAgent
from population.agents import SASPopulationAgent, AFRPopulationAgent, EURPopulationAgent
from retrieval.evidence.retriever import EvidenceRetriever
from retrieval.planner.query_planner import QueryPlanner
from retrieval.evidence.synthesizer import EvidenceSynthesizer
from verification.engine import VerificationEngine

# Off-by-default: set ANUKRITI_REAL_FREQUENCIES=1 to overlay gnomAD/SGDP data.
_USE_REAL = os.environ.get("ANUKRITI_REAL_FREQUENCIES", "") == "1"


# --- ADK Tool Functions ---
# Each function is a tool that the Gemini orchestrator can invoke.

def tool_population_analysis(gene: str, allele: str, population: str) -> dict[str, Any]:
    """ADK Tool: Population-aware allele frequency analysis.

    Returns frequency, rarity, clinical note, and prevalence data.
    DETERMINISTIC — no LLM involved.
    """
    agents = {
        "SAS": SASPopulationAgent(use_gnomad=_USE_REAL, use_sgdp=_USE_REAL),
        "AFR": AFRPopulationAgent(use_gnomad=_USE_REAL, use_sgdp=_USE_REAL),
        "EUR": EURPopulationAgent(use_gnomad=_USE_REAL, use_sgdp=_USE_REAL),
    }
    agent = agents.get(population)
    if not agent:
        return {"error": f"Unknown population: {population}", "origin": "deterministic"}

    result = agent.reason(gene, allele)
    return {
        "population": result.population,
        "frequency": result.frequency.frequency,
        "rarity": result.risk_context.rarity_class,
        "clinical_note": result.risk_context.clinical_note,
        "confidence": result.confidence,
        "prevalence": [{"phenotype": p.phenotype, "prevalence": p.prevalence} for p in result.prevalence_estimates],
        "origin": "deterministic",
    }


def tool_pharmacogene_analysis(gene: str, allele1: str, allele2: str) -> dict[str, Any]:
    """ADK Tool: Deterministic pharmacogene phenotype inference.

    Returns phenotype, risk, activity score, and CPIC recommendations.
    DETERMINISTIC — CPIC activity score rules, no LLM.
    """
    agents = {"CYP2C19": CYP2C19Agent(), "CYP2D6": CYP2D6Agent()}
    agent = agents.get(gene)
    if not agent:
        return {"error": f"Unknown gene: {gene}", "origin": "deterministic"}

    analysis = agent.analyze_diplotype(allele1, allele2)
    return {
        "gene": analysis.gene,
        "diplotype": analysis.diplotype,
        "activity_score": analysis.phenotype_inference.activity_score,
        "phenotype": analysis.phenotype_inference.phenotype,
        "risk": analysis.risk_classification,
        "confidence": analysis.confidence,
        "recommendations": [
            {"drug": r.drug, "recommendation": r.recommendation, "strength": r.strength, "pmid": r.pmid}
            for r in analysis.recommendations
        ],
        "provenance": analysis.provenance,
        "origin": "deterministic",
    }


def tool_hla_risk_assessment(has_allele: bool) -> dict[str, Any]:
    """ADK Tool: HLA-B*15:02 binary risk assessment.

    DETERMINISTIC — presence/absence determines contraindication.
    """
    agent = HLABAgent()
    result = agent.assess_risk(has_allele)
    return {
        "allele_status": result.allele_status,
        "risk_level": result.risk_level,
        "drugs_affected": result.drugs_affected,
        "recommendations": [{"drug": r.drug, "recommendation": r.recommendation} for r in result.recommendations],
        "origin": "deterministic",
    }


def tool_evidence_retrieval(gene: str, drug: str, population: str | None = None) -> dict[str, Any]:
    """ADK Tool: MA-RAG evidence retrieval with citation tracking.

    DETERMINISTIC — searches indexed evidence, returns grounded claims.
    """
    planner = QueryPlanner()
    retriever = EvidenceRetriever()
    synthesizer = EvidenceSynthesizer()

    plan = planner.plan(f"{gene} {drug} pharmacogenomics", gene=gene, drug=drug, population=population)
    result = retriever.execute_plan(plan)
    synthesis = synthesizer.synthesize(result)

    return {
        "citations": [c.citation_id for c in result.citations],
        "grounding_score": synthesis.grounding_score,
        "claims": [{"claim": c.claim[:150], "citations": c.citations, "grounded": c.grounded} for c in synthesis.claims],
        "total_retrieved": result.total_retrieved,
        "origin": "deterministic",
    }


def tool_verification(output: dict[str, Any], claims: list[dict] | None = None) -> dict[str, Any]:
    """ADK Tool: Safety verification with TAO escalation.

    Runs 6 checks on agent output. DETERMINISTIC.
    """
    engine = VerificationEngine()
    report = engine.verify(output, claims=claims)
    return {
        "verdict": report.overall_verdict.value,
        "confidence": report.confidence.value if report.confidence else 0,
        "confidence_level": report.confidence.level.value if report.confidence else "unknown",
        "escalation_tier": report.escalation.tier.value if report.escalation else "unknown",
        "checks": [{"name": c.check_name, "verdict": c.verdict.value} for c in report.checks],
        "origin": "deterministic",
    }


# --- Tool Registry for ADK ---

ADK_TOOLS = {
    "population_analysis": tool_population_analysis,
    "pharmacogene_analysis": tool_pharmacogene_analysis,
    "hla_risk_assessment": tool_hla_risk_assessment,
    "evidence_retrieval": tool_evidence_retrieval,
    "verification": tool_verification,
}
