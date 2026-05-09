"""Anukriti Swarm — production evaluation + benchmarking framework.

Structured evaluation of the swarm's reliability, grounding quality,
orchestration correctness, and biomedical safety. This package is
**additive** and **composable**: it wraps the existing benchmark
scenarios, safety engine, observability, and MCP layers into six
purpose-built evaluation suites + one aggregate report.

Layered on top of (not replacing):

    benchmarks.scenarios         12 CPIC scenarios across 3 genes ×
                                  4 populations (session 0)
    benchmarks.adversarial       4 adversarial scenarios
                                  (conflicting / ambiguous / missing
                                  evidence / ancestry edge, session 2)
    agents.verification          BiomedicalVerificationAgent
                                  (session 2 safety engine)
    core.verification            5-tier scoring + claim validator +
                                  grounding engine + safety engine +
                                  provenance validator (session 2)
    observability                ExecutionTracer + FailureAnalyzer +
                                  TimingProfiler (session 3)
    metrics.collector            MetricsCollector / PipelineMetrics

Planned public surface (lands progressively across the 12 commits):

    EvaluationCase / EvaluationResult / EvaluationSuite   base types
    OrchestrationAccuracySuite     phenotype / risk / verdict correctness
    VerificationAccuracySuite      safety engine outcome matches expected
    EvidenceGroundingSuite         grounding rate + unsupported-claim rate
    HallucinationPreventionSuite   block rate on adversarial inputs
    PopulationAwareSuite           cross-population reasoning correctness
    WorkflowReliabilitySuite       end-to-end completion + failure rate

    SwarmEvaluationReport          aggregate report with markdown +
                                    JSON renderers

Design principles:

1. **Reproducible.** Every suite is a pure function of its scenario
   list + the orchestrator/agent under test. Same inputs → same
   numbers, always.
2. **Non-destructive.** No modifications to benchmarks/, metrics/,
   agents/, or core/. The evaluation framework is a read-only
   consumer.
3. **Publication-oriented.** Every suite produces structured
   metrics + human-readable summaries. The aggregate report
   renders to markdown suitable for a whitepaper or hackathon
   submission.
"""

from __future__ import annotations

from evaluation.base import (
    EvaluationCase,
    EvaluationResult,
    EvaluationSuite,
    SuiteSummary,
)

__all__: list[str] = [
    "EvaluationCase",
    "EvaluationResult",
    "EvaluationSuite",
    "SuiteSummary",
]
