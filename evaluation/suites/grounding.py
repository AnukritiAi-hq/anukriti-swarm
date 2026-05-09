"""``EvidenceGroundingSuite`` — closes req #2.3 and parts of req #4.

Runs each case through the orchestrator + MCP persistence hook so
the evidence cache is populated, then pipes the run through
EvidenceGroundingEngine.ground_run(). Per-case metrics carry the
4-tuple (grounded / partial / unresolved claims) + coverage ratio.

Aggregates surface two headline numbers the brief requires:

    grounding_rate           fraction of (case, source) pairs
                              that resolved in the MCP evidence cache
    unsupported_claim_rate   fraction of claims whose grounding state
                              ended up 'fail' (zero resolved sources)

A case passes when its grounding coverage meets the configured
``pass_threshold`` (default 0.5). Setting the threshold to 1.0
makes the suite strict (every claim must be fully grounded);
0.0 makes it permissive (pass even with zero grounding).

Design note
-----------
This suite relies on MCPPersistenceHook populating the evidence
cache before grounding runs. The hook writes retrieval_results
into the cache; claims that cite guideline_ids (e.g.
``CPIC:CYP2C19:clopidogrel:2022``) that aren't indexed will
surface as missing — and that's expected signal, not a bug.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from agents.orchestrator.gemini_orchestrator import GeminiOrchestrator
from core.verification.claim_validator import BiomedicalClaimValidator
from core.verification.grounding import EvidenceGroundingEngine
from integrations.mcp import MCPClient, MCPPersistenceHook

from evaluation.base import EvaluationCase, EvaluationResult, EvaluationSuite


@dataclass
class EvidenceGroundingSuite(EvaluationSuite):
    """Per-case grounding pass with aggregate grounding + unsupported rates."""

    name: str = "evidence_grounding"
    pass_threshold: float = 0.5    # coverage >= threshold -> pass
    client: MCPClient | None = None
    orchestrator: GeminiOrchestrator | None = None
    hook: MCPPersistenceHook | None = None
    validator: BiomedicalClaimValidator | None = None
    engine: EvidenceGroundingEngine | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = MCPClient()
        if self.orchestrator is None:
            self.orchestrator = GeminiOrchestrator()
        if self.hook is None:
            self.hook = MCPPersistenceHook(client=self.client)
        if self.validator is None:
            self.validator = BiomedicalClaimValidator()
        if self.engine is None:
            self.engine = EvidenceGroundingEngine(
                client=self.client, validator=self.validator
            )

    # ------------------------------------------------------------------
    # Suite contract
    # ------------------------------------------------------------------

    def run_case(self, case: EvaluationCase) -> EvaluationResult:
        t0 = time.perf_counter()
        inp = case.input
        try:
            result = self.orchestrator.run(
                gene=inp.get("gene", ""),
                drug=inp.get("drug", ""),
                population=inp.get("population", ""),
                allele1=inp.get("allele1"),
                allele2=inp.get("allele2"),
            )
        except Exception as exc:
            return EvaluationResult(
                case_id=case.case_id,
                suite_name=self.name,
                passed=False,
                expected=dict(case.expected),
                errors=(f"orchestrator.run: {type(exc).__name__}: {exc}",),
                reason="orchestration crashed",
                duration_ms=(time.perf_counter() - t0) * 1000,
            )

        # Persist so MCP evidence cache has the run's citations.
        self.hook.persist(result)

        run0 = (
            result.coordination.runs[0]
            if result.coordination.runs
            else {}
        )
        traces, report = self.engine.ground_run(
            run0, correlation_id=result.context.correlation_id
        )
        duration_ms = (time.perf_counter() - t0) * 1000

        coverage = report.coverage
        passed = coverage >= self.pass_threshold

        # Per-claim grounding outcome histogram.
        claim_states: dict[str, int] = {"pass": 0, "warn": 0, "fail": 0}
        for t in traces:
            claim_states[t.state] = claim_states.get(t.state, 0) + 1

        return EvaluationResult(
            case_id=case.case_id,
            suite_name=self.name,
            passed=passed,
            observed={
                "coverage": coverage,
                "sources_requested": report.sources_requested,
                "sources_resolved": report.sources_resolved,
                "missing_source_ids": list(report.missing_source_ids),
                "claims_fully_grounded": report.claims_fully_grounded,
                "claims_partially_grounded": report.claims_partially_grounded,
                "claims_unresolved": report.claims_unresolved,
                "claim_states": claim_states,
            },
            expected=dict(case.expected),
            metrics={
                "coverage": coverage,
                "sources_requested": report.sources_requested,
                "sources_resolved": report.sources_resolved,
                "claims_unresolved": report.claims_unresolved,
                "claims_fully_grounded": report.claims_fully_grounded,
            },
            reason=(
                f"coverage={coverage:.0%} "
                f"({report.sources_resolved}/{report.sources_requested}) "
                f"— threshold={self.pass_threshold:.0%}"
            ),
            duration_ms=duration_ms,
        )

    def aggregate(self, results: list[EvaluationResult]) -> dict[str, Any]:
        total_requested = sum(
            int(r.metrics.get("sources_requested") or 0) for r in results
        )
        total_resolved = sum(
            int(r.metrics.get("sources_resolved") or 0) for r in results
        )
        # Claims across all three grounding states — need the
        # partially_grounded count on the observed dict, which we
        # didn't expose in metrics. Pull from observed instead.
        total_claims = 0
        unresolved_claims = 0
        fully_grounded = 0
        for r in results:
            obs = r.observed or {}
            fully_grounded += int(obs.get("claims_fully_grounded") or 0)
            partial = int(obs.get("claims_partially_grounded") or 0)
            unresolved = int(obs.get("claims_unresolved") or 0)
            unresolved_claims += unresolved
            total_claims += fully_grounded + partial + unresolved - (fully_grounded if False else 0)
        # The line above was defensive-written; simpler rewrite:
        total_claims = 0
        for r in results:
            obs = r.observed or {}
            total_claims += (
                int(obs.get("claims_fully_grounded") or 0)
                + int(obs.get("claims_partially_grounded") or 0)
                + int(obs.get("claims_unresolved") or 0)
            )
        mean_coverage = (
            sum(float(r.metrics.get("coverage") or 0.0) for r in results) / len(results)
            if results
            else 0.0
        )
        grounding_rate = (
            total_resolved / total_requested if total_requested else 1.0
        )
        unsupported_claim_rate = (
            unresolved_claims / total_claims if total_claims else 0.0
        )
        return {
            "grounding_rate": round(grounding_rate, 4),
            "unsupported_claim_rate": round(unsupported_claim_rate, 4),
            "mean_coverage": round(mean_coverage, 4),
            "total_sources_requested": total_requested,
            "total_sources_resolved": total_resolved,
            "total_claims_tracked": total_claims,
            "total_claims_unresolved": unresolved_claims,
            "pass_threshold": self.pass_threshold,
        }


__all__ = ["EvidenceGroundingSuite"]
