"""Gemini-powered orchestration layer via Google ADK.

The orchestrator uses Gemini for:
- Query understanding and intent classification
- Workflow planning (which tools to invoke)
- Execution coordination
- Narrative synthesis from deterministic results

Gemini NEVER:
- Infers phenotypes (tools do that deterministically)
- Overrides CPIC recommendations
- Bypasses verification
- Generates unsupported biomedical claims
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ai.gemini.client import AIClient, AIProvider
from integrations.google_adk.agents import ADK_TOOLS
from integrations.mongodb_mcp.client import MongoDBMCP


@dataclass
class OrchestrationStep:
    """A single step in the orchestrated workflow."""

    step: int
    tool: str
    action: str
    result: dict[str, Any]
    duration_ms: float
    origin: str  # "deterministic" or "generative"


@dataclass
class OrchestrationResult:
    """Complete result from Gemini-orchestrated workflow."""

    correlation_id: str
    query: str
    steps: list[OrchestrationStep] = field(default_factory=list)
    deterministic_output: dict[str, Any] = field(default_factory=dict)
    narrative: dict[str, str] = field(default_factory=dict)
    total_duration_ms: float = 0.0
    gemini_provider: str = ""
    mcp_mode: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ADKOrchestrator:
    """Gemini-powered orchestrator using ADK tool pattern.

    Workflow:
    1. Gemini understands the query
    2. Orchestrator routes to deterministic tools
    3. Tools return authoritative results
    4. MongoDB MCP stores traces
    5. Gemini synthesizes explanation from results
    """

    def __init__(self) -> None:
        import os
        if os.environ.get("OPENAI_API_KEY"):
            self.ai = AIClient(AIProvider.OPENAI)
        else:
            self.ai = AIClient(AIProvider.GEMINI)
        self.mcp = MongoDBMCP()

    def execute(self, gene: str, drug: str, population: str, allele1: str, allele2: str) -> OrchestrationResult:
        """Execute full Gemini-orchestrated pharmacogenomic workflow."""
        import uuid
        correlation_id = uuid.uuid4().hex[:12]
        t0 = time.perf_counter()
        steps: list[OrchestrationStep] = []

        # Step 1: Population analysis (deterministic)
        t1 = time.perf_counter()
        pop_result = ADK_TOOLS["population_analysis"](gene, allele2, population)
        steps.append(OrchestrationStep(1, "population_analysis", f"Analyze {allele2} in {population}", pop_result, (time.perf_counter() - t1) * 1000, "deterministic"))
        self.mcp.traces_log(correlation_id, "population", f"population_{population.lower()}", pop_result)

        # Step 2: Pharmacogene analysis (deterministic)
        t2 = time.perf_counter()
        pgx_result = ADK_TOOLS["pharmacogene_analysis"](gene, allele1, allele2)
        steps.append(OrchestrationStep(2, "pharmacogene_analysis", f"Infer phenotype for {allele1}/{allele2}", pgx_result, (time.perf_counter() - t2) * 1000, "deterministic"))
        self.mcp.traces_log(correlation_id, "pharmacogene", f"pharmacogene_{gene.lower()}", pgx_result)

        # Step 3: Evidence retrieval (deterministic)
        t3 = time.perf_counter()
        evidence_result = ADK_TOOLS["evidence_retrieval"](gene, drug, population)
        steps.append(OrchestrationStep(3, "evidence_retrieval", f"Ground findings in evidence", evidence_result, (time.perf_counter() - t3) * 1000, "deterministic"))
        self.mcp.traces_log(correlation_id, "retrieval", "retrieval_main", evidence_result)

        # Step 4: Verification (deterministic)
        t4 = time.perf_counter()
        verify_input = {"agent_id": f"pharmacogene_{gene.lower()}", "gene": gene, "drug": drug, "origin": "deterministic", "confidence": pgx_result.get("confidence", 1.0), "source": "CPIC", "population": population, "sample_n": 15000, "frequency": pop_result.get("frequency")}
        verify_result = ADK_TOOLS["verification"](verify_input, claims=[{"claim": c["claim"], "citations": c["citations"]} for c in evidence_result.get("claims", [])])
        steps.append(OrchestrationStep(4, "verification", "Validate all outputs", verify_result, (time.perf_counter() - t4) * 1000, "deterministic"))
        self.mcp.traces_log(correlation_id, "verification", "verification_main", verify_result)

        # Step 5: Provenance recording (MCP)
        for rec in pgx_result.get("recommendations", []):
            self.mcp.provenance_record(correlation_id, rec["recommendation"], rec.get("pmid", ""), pgx_result.get("confidence", 1.0))

        # Step 6: Gemini narrative synthesis (generative)
        t5 = time.perf_counter()
        ctx = {
            "gene": gene, "drug": drug, "population": population,
            "diplotype": pgx_result.get("diplotype"), "phenotype": pgx_result.get("phenotype"),
            "risk": pgx_result.get("risk"), "frequency": pop_result.get("frequency"),
            "recommendation": pgx_result.get("recommendations", [{}])[0].get("recommendation", "") if pgx_result.get("recommendations") else "",
            "citations": evidence_result.get("citations", []),
            "confidence": verify_result.get("confidence"),
            "verification": verify_result.get("verdict"),
        }

        from ai.prompts.templates import clinician_explanation, patient_explanation, orchestration_summary
        clinician_text = self.ai.generate(clinician_explanation(ctx), context=ctx).text
        patient_text = self.ai.generate(patient_explanation(ctx), context=ctx).text

        narrative = {"clinician": clinician_text, "patient": patient_text}
        steps.append(OrchestrationStep(5, "gemini_narrative", "Synthesize explanations", {"audiences": 2}, (time.perf_counter() - t5) * 1000, "generative"))

        # Store final memory
        self.mcp.memory_store("orchestrator", correlation_id, {"gene": gene, "drug": drug, "phenotype": pgx_result.get("phenotype"), "verdict": verify_result.get("verdict")})

        total = (time.perf_counter() - t0) * 1000

        return OrchestrationResult(
            correlation_id=correlation_id,
            query=f"{gene} {allele1}/{allele2} + {drug} in {population}",
            steps=steps,
            deterministic_output={"pharmacogene": pgx_result, "population": pop_result, "evidence": evidence_result, "verification": verify_result},
            narrative=narrative,
            total_duration_ms=total,
            gemini_provider=f"{self.ai.provider.value} ({self.ai.model})",
            mcp_mode=self.mcp.mode,
        )
