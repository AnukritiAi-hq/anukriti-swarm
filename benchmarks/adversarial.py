"""Adversarial benchmark scenarios for the deterministic safety engine.

Closes requirement #10 of the safety brief. Four scenario kinds
exercise the specific failure paths the safety engine must catch:

    conflicting_evidence  two contradictory recommendations for the
                          same drug — SafetyConstraintEngine's
                          recommendation_consistency check should
                          fire (tier=CONFLICTING, block=True)

    ambiguous_genotype    a diplotype that maps to an edge-of-range
                          activity score, or a phenotype different
                          from what infer_phenotype() produces —
                          phenotype_correctness catches this
                          (tier=UNSAFE, block=True)

    missing_evidence      claim cites evidence ids the MCP evidence
                          cache doesn't know about — EvidenceGrounding
                          engine emits zero-grounding FAIL or a low
                          coverage WARN (tier=UNVERIFIED, reroute)

    ancestry_edge_case    a rare-population diplotype with no
                          prevalence data (sparse_population_data
                          check WARN) or an unknown allele
                          (allele_interpretation FAIL)

Each scenario carries:

    - a ``run_dict`` shaped like ``CoordinationResult.runs[i]`` —
      the same shape the agent consumes. Lets the safety engine
      be exercised without running the full orchestrator.
    - an ``expected_safe`` boolean — what the engine *should* say
    - an ``expected_tier`` + ``expected_block`` pair — what tier /
      block decision the engine *should* produce
    - an ``expected_actions`` list — which EscalationActions should
      appear in the workflow plan

``run_all(agent, workflow)`` iterates every scenario, runs the
agent + workflow, and returns a list of results the demo and
the smoke-test harness can consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.verification.agent import BiomedicalVerificationAgent, VerificationOutcome
from core.verification.escalation_workflow import (
    EscalationAction,
    EscalationPlan,
    EscalationWorkflow,
)
from core.verification.scoring import VerificationTier


# ---------------------------------------------------------------------------
# Scenario shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdversarialScenario:
    """One adversarial run the safety engine must handle correctly."""

    scenario_id: str
    kind: str                  # conflicting | ambiguous | missing | ancestry
    description: str
    run_dict: dict[str, Any]
    expected_safe: bool
    expected_tier: VerificationTier
    expected_block: bool
    expected_actions: tuple[EscalationAction, ...] = ()


@dataclass
class ScenarioResult:
    """What actually happened when we ran the scenario."""

    scenario_id: str
    kind: str
    description: str
    outcome: VerificationOutcome
    plan: EscalationPlan
    passed: bool               # expectations matched observed?
    mismatches: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "kind": self.kind,
            "description": self.description,
            "passed": self.passed,
            "mismatches": list(self.mismatches),
            "observed": {
                "is_safe": self.outcome.is_safe,
                "tier": self.outcome.tier,
                "block": (
                    self.outcome.decision.block
                    if self.outcome.decision else None
                ),
                "plan_status": self.plan.status,
                "step_count": len(self.plan.steps),
            },
        }


# ---------------------------------------------------------------------------
# Scenario catalog
# ---------------------------------------------------------------------------


ADVERSARIAL_SCENARIOS: list[AdversarialScenario] = [
    # ----------------------------------------------------------------
    # 1. CONFLICTING EVIDENCE
    #    Two recommendations for the same drug (clopidogrel) that
    #    give opposite actions. The recommendation_consistency check
    #    must fire.
    # ----------------------------------------------------------------
    AdversarialScenario(
        scenario_id="conflicting_evidence_clopidogrel",
        kind="conflicting",
        description=(
            "CYP2C19 *2/*2 + clopidogrel in SAS with two opposing "
            "recommendations for the same drug."
        ),
        run_dict={
            "gene": "CYP2C19",
            "drug": "clopidogrel",
            "allele1": "*2",
            "allele2": "*2",
            "pharmacogene_result": {
                "gene": "CYP2C19",
                "phenotype": "Poor Metabolizer",
                "confidence": 1.0,
                "provenance": {"guideline_source": "CPIC"},
            },
            "recommendations": [
                {
                    "drug": "clopidogrel",
                    "recommendation": "Use standard dose of clopidogrel",
                    "guideline_id": "CPIC:CYP2C19:clopidogrel:2022",
                    "pmid": "PMID:34032273",
                },
                {
                    "drug": "clopidogrel",
                    "recommendation": (
                        "Avoid clopidogrel — use prasugrel or ticagrelor instead"
                    ),
                    "guideline_id": "CPIC:CYP2C19:clopidogrel:2022",
                    "pmid": "PMID:34032273",
                },
            ],
            "citations": ["PMID:34032273"],
        },
        expected_safe=False,
        expected_tier=VerificationTier.CONFLICTING,
        expected_block=True,
        expected_actions=(EscalationAction.BLOCK,),
    ),

    # ----------------------------------------------------------------
    # 2. AMBIGUOUS GENOTYPE — phenotype drift
    #    *1/*1 is Normal Metabolizer per infer_phenotype() — stating
    #    'Poor Metabolizer' here is a silent drift that the
    #    phenotype_correctness check must block.
    # ----------------------------------------------------------------
    AdversarialScenario(
        scenario_id="ambiguous_genotype_phenotype_drift",
        kind="ambiguous",
        description=(
            "CYP2C19 *1/*1 stated as Poor Metabolizer (rule output is "
            "Normal Metabolizer) — phenotype-claim drift."
        ),
        run_dict={
            "gene": "CYP2C19",
            "drug": "clopidogrel",
            "allele1": "*1",
            "allele2": "*1",
            "pharmacogene_result": {
                "gene": "CYP2C19",
                "phenotype": "Poor Metabolizer",  # WRONG per rule
                "confidence": 1.0,
                "provenance": {"guideline_source": "CPIC"},
            },
            "recommendations": [
                {
                    "drug": "clopidogrel",
                    "recommendation": "Use alternative antiplatelet agent",
                    "guideline_id": "CPIC:CYP2C19:clopidogrel:2022",
                    "pmid": "PMID:34032273",
                },
            ],
            "citations": ["PMID:34032273"],
        },
        expected_safe=False,
        expected_tier=VerificationTier.UNSAFE,
        expected_block=True,
        expected_actions=(EscalationAction.BLOCK,),
    ),

    # ----------------------------------------------------------------
    # 3. MISSING EVIDENCE
    #    Every cited source id is fabricated — none resolve in the
    #    MCP evidence cache. GroundingEngine must FAIL; the workflow
    #    must emit REQUEST_EVIDENCE for each missing source.
    # ----------------------------------------------------------------
    AdversarialScenario(
        scenario_id="missing_evidence_fabricated_pmids",
        kind="missing",
        description=(
            "CYP2C19 *2/*2 + clopidogrel citing two fabricated PMIDs "
            "that don't exist in the MCP evidence cache."
        ),
        run_dict={
            "gene": "CYP2C19",
            "drug": "clopidogrel",
            "allele1": "*2",
            "allele2": "*2",
            "pharmacogene_result": {
                "gene": "CYP2C19",
                "phenotype": "Poor Metabolizer",
                "confidence": 1.0,
                "provenance": {"guideline_source": "CPIC"},
            },
            "recommendations": [
                {
                    "drug": "clopidogrel",
                    "recommendation": "Use alternative antiplatelet agent",
                    "guideline_id": "CPIC:CYP2C19:clopidogrel:2022",
                    "pmid": "PMID:99999999",  # fabricated
                },
            ],
            "citations": ["PMID:99999999", "FAKE:EVIDENCE:1"],
        },
        expected_safe=True,   # UNVERIFIED alone doesn't hard-block
                              # the engine — the workflow escalates
        # The tier depends on the grounding cache state. With a fresh
        # empty cache, every claim fails grounding → UNVERIFIED.
        # With a populated cache missing just these two, partial
        # grounding may land us at UNVERIFIED via grounding FAIL.
        expected_tier=VerificationTier.UNVERIFIED,
        expected_block=False,   # UNVERIFIED alone doesn't hard-block,
                                # but the plan still requests evidence.
        expected_actions=(EscalationAction.REQUEST_EVIDENCE,),
    ),

    # ----------------------------------------------------------------
    # 4. ANCESTRY EDGE CASE — unknown allele in a rare population
    #    *99 doesn't exist in ALLELE_ACTIVITY_SCORES. The
    #    allele_interpretation check must FAIL; infer_phenotype
    #    returns 'Indeterminate' so the phenotype_correctness path
    #    short-circuits.
    # ----------------------------------------------------------------
    AdversarialScenario(
        scenario_id="ancestry_edge_unknown_allele",
        kind="ancestry",
        description=(
            "CYP2C19 *99 (synthetic unknown allele) in an ancestry-edge "
            "population — allele_interpretation must FAIL."
        ),
        run_dict={
            "gene": "CYP2C19",
            "drug": "clopidogrel",
            "allele1": "*99",     # unknown — not in ALLELE_ACTIVITY_SCORES
            "allele2": "*1",
            "pharmacogene_result": {
                "gene": "CYP2C19",
                "phenotype": "Indeterminate",
                "confidence": 0.0,
                "provenance": {"guideline_source": "CPIC"},
            },
            "recommendations": [],
            "citations": ["PMID:34032273"],
        },
        expected_safe=True,   # UNVERIFIED doesn't hard-block
        expected_tier=VerificationTier.UNVERIFIED,
        expected_block=False,
        expected_actions=(EscalationAction.REROUTE,),
    ),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_scenario(
    scenario: AdversarialScenario,
    agent: BiomedicalVerificationAgent,
    workflow: EscalationWorkflow,
    *,
    correlation_id_prefix: str = "adv",
) -> ScenarioResult:
    """Execute one scenario and compare observed to expected."""
    cid = f"{correlation_id_prefix}-{scenario.scenario_id}"
    outcome = agent.verify_run(scenario.run_dict, correlation_id=cid)
    plan = workflow.plan(outcome)

    mismatches: list[str] = []
    if outcome.is_safe != scenario.expected_safe:
        mismatches.append(
            f"is_safe: expected={scenario.expected_safe} "
            f"observed={outcome.is_safe}"
        )
    if outcome.tier != scenario.expected_tier.value:
        mismatches.append(
            f"tier: expected={scenario.expected_tier.value} "
            f"observed={outcome.tier}"
        )
    if outcome.decision and outcome.decision.block != scenario.expected_block:
        mismatches.append(
            f"block: expected={scenario.expected_block} "
            f"observed={outcome.decision.block}"
        )
    observed_actions = {s.action for s in plan.steps}
    for expected_action in scenario.expected_actions:
        if expected_action not in observed_actions:
            mismatches.append(
                f"missing expected action: {expected_action.value}"
            )

    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        kind=scenario.kind,
        description=scenario.description,
        outcome=outcome,
        plan=plan,
        passed=not mismatches,
        mismatches=tuple(mismatches),
    )


def run_all(
    agent: BiomedicalVerificationAgent,
    workflow: EscalationWorkflow | None = None,
    *,
    scenarios: list[AdversarialScenario] | None = None,
) -> list[ScenarioResult]:
    """Run every adversarial scenario; return a list of results.

    ``scenarios`` defaults to the full ``ADVERSARIAL_SCENARIOS`` set;
    pass a subset to run only specific kinds (e.g. just
    ``[ADVERSARIAL_SCENARIOS[1]]`` for the phenotype-drift test).
    """
    wf = workflow or EscalationWorkflow()
    catalog = scenarios or ADVERSARIAL_SCENARIOS
    return [run_scenario(s, agent, wf) for s in catalog]


__all__ = [
    "AdversarialScenario",
    "ScenarioResult",
    "ADVERSARIAL_SCENARIOS",
    "run_scenario",
    "run_all",
]
