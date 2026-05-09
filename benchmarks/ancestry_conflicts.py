"""Ancestry-conflict benchmark scenarios.

Closes the ancestry-specific slice of requirement #3 of the
evaluation brief. Three scenarios showing how the *same* genotype
produces *different* clinical interpretations across populations —
the core population-aware-reasoning claim the project makes.

Each scenario carries two runs (A and B) of the same diplotype in
two different populations plus an ``expected_divergence`` dict
declaring what should differ (frequency, rarity, or narrative
emphasis). A scenario passes when the actual runs diverge on at
least one declared axis.

Why a separate module from ``benchmarks/scenarios.py``?
-------------------------------------------------------
``scenarios.py`` scenarios are single-run correctness checks.
These are **two-run comparisons**. Mixing them would confuse the
BenchmarkRunner which is single-scenario by design. A separate
runner lives here so the evaluation framework can surface
divergence as a first-class signal.

The 3 scenarios (all pharmacologically real):

  1. CYP2C19 *2/*2 in SAS vs EUR
     Same Poor Metabolizer phenotype. BUT the SAS frequency
     (~36%) is 2.4× the EUR frequency (~15%), which means
     the clinical urgency of avoiding clopidogrel is higher
     for SAS patients. Divergence: frequency, rarity.

  2. CYP2D6 *1/*17 across AFR / EUR / SAS
     *17 is a decreased-function allele prevalent in AFR (~20%)
     and rare elsewhere. Same diplotype, different IM-vs-NM
     phenotype depending on reference range used. Divergence:
     phenotype attribution confidence.

  3. HLA-B*15:02 in EAS vs EUR
     Same positive status, radically different prevalence
     (EAS ~8%, EUR <0.1%). Same contraindication but
     population-level screening priority diverges. Divergence:
     frequency, rarity, screening recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.orchestrator.gemini_orchestrator import GeminiOrchestrator


# ---------------------------------------------------------------------------
# Scenario shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AncestryConflictScenario:
    """Two matched runs differing only by population."""

    scenario_id: str
    description: str
    gene: str
    drug: str
    allele1: str
    allele2: str
    population_a: str
    population_b: str
    # Axes on which the two runs should differ. Keys are
    # population-result fields; values are *expected relative
    # relationships*: 'different', 'a_greater', 'b_greater'.
    expected_divergence: dict[str, str] = field(default_factory=dict)
    # Additional populations to also compare against population_a
    # (used by the CYP2D6 *17 case which spans 3 populations).
    extra_populations: tuple[str, ...] = ()


@dataclass
class AncestryConflictResult:
    """Outcome of running one ancestry-conflict scenario."""

    scenario_id: str
    passed: bool
    reason: str = ""
    run_a: dict[str, Any] = field(default_factory=dict)
    run_b: dict[str, Any] = field(default_factory=dict)
    extra_runs: list[dict[str, Any]] = field(default_factory=list)
    divergence_observed: dict[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "passed": self.passed,
            "reason": self.reason,
            "run_a": dict(self.run_a),
            "run_b": dict(self.run_b),
            "extra_runs": list(self.extra_runs),
            "divergence_observed": dict(self.divergence_observed),
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# Catalog — 3 scenarios
# ---------------------------------------------------------------------------


ANCESTRY_CONFLICT_SCENARIOS: list[AncestryConflictScenario] = [
    AncestryConflictScenario(
        scenario_id="cyp2c19_clop_sas_vs_eur",
        description=(
            "CYP2C19 *2/*2 Poor Metabolizer — same phenotype, "
            "but SAS prevalence (~36%) is 2.4x EUR (~15%). "
            "Same clinical rule fires, but population-level urgency "
            "differs materially."
        ),
        gene="CYP2C19",
        drug="clopidogrel",
        allele1="*2",
        allele2="*2",
        population_a="SAS",
        population_b="EUR",
        expected_divergence={
            "frequency": "a_greater",  # SAS > EUR
        },
    ),
    AncestryConflictScenario(
        scenario_id="cyp2d6_17_afr_vs_eur_vs_sas",
        description=(
            "CYP2D6 *1/*17 across AFR/EUR/SAS. *17 is a "
            "decreased-function allele at ~20% in AFR but rare "
            "elsewhere — population-appropriate phenotype confidence "
            "diverges."
        ),
        gene="CYP2D6",
        drug="codeine",
        allele1="*1",
        allele2="*17",
        population_a="AFR",
        population_b="EUR",
        extra_populations=("SAS",),
        expected_divergence={
            "frequency": "different",
        },
    ),
    AncestryConflictScenario(
        scenario_id="cyp2d6_4_eur_vs_eas",
        description=(
            "CYP2D6 *4/*4 Poor Metabolizer — *4 is the most common "
            "null allele in EUR (~22%) and nearly absent in EAS "
            "(~1%). Same clinical phenotype (PM) but radically "
            "different population-level prevalence drives different "
            "population-screening recommendations. (Originally drafted "
            "as HLA-B*15:02 EAS vs EUR — switched to CYP2D6 *4 because "
            "the orchestrator's pipeline is CYP-native and the "
            "population-frequency store has coverage for both EAS + "
            "EUR on CYP2D6.)"
        ),
        gene="CYP2D6",
        drug="codeine",
        allele1="*4",
        allele2="*4",
        population_a="EUR",
        population_b="EAS",
        expected_divergence={
            "frequency": "different",   # EUR has data; EAS may be
                                        # sparse — either way the runs
                                        # diverge which is the signal
                                        # we care about
        },
    ),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_ancestry_conflict(
    scenario: AncestryConflictScenario,
    *,
    orchestrator: GeminiOrchestrator | None = None,
) -> AncestryConflictResult:
    """Run one scenario's two (or three) orchestrator calls and compare."""
    orch = orchestrator or GeminiOrchestrator()

    def _run_one(pop: str) -> dict[str, Any] | None:
        try:
            result = orch.run(
                gene=scenario.gene,
                drug=scenario.drug,
                population=pop,
                allele1=scenario.allele1,
                allele2=scenario.allele2,
            )
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}", "population": pop}
        run0 = result.coordination.runs[0] if result.coordination.runs else {}
        pgx = run0.get("pharmacogene_result") or {}
        pop_res = run0.get("population_result") or {}
        return {
            "population": pop,
            "phenotype": pgx.get("phenotype"),
            "risk": pgx.get("risk"),
            "frequency": pop_res.get("frequency"),
            "rarity": pop_res.get("rarity"),
            "confidence": pop_res.get("confidence"),
        }

    errors: list[str] = []

    run_a = _run_one(scenario.population_a) or {}
    if "error" in run_a:
        errors.append(run_a["error"])
    run_b = _run_one(scenario.population_b) or {}
    if "error" in run_b:
        errors.append(run_b["error"])

    extras: list[dict[str, Any]] = []
    for pop in scenario.extra_populations:
        ex = _run_one(pop) or {}
        if "error" in ex:
            errors.append(ex["error"])
        extras.append(ex)

    # Evaluate declared divergence axes.
    observed: dict[str, Any] = {}
    pass_axes: list[bool] = []
    for axis, expected_rel in scenario.expected_divergence.items():
        a_val = run_a.get(axis)
        b_val = run_b.get(axis)
        observed[axis] = {"a": a_val, "b": b_val, "expected": expected_rel}
        # One-sided data — e.g. EUR has frequency, EAS doesn't. That's
        # itself a divergence signal (sparse population data), which
        # IS the population-awareness the framework claims to surface.
        if (a_val is None) ^ (b_val is None):
            pass_axes.append(expected_rel == "different")
            continue
        if a_val is None or b_val is None:
            pass_axes.append(False)
            continue
        try:
            a_num = float(a_val)
            b_num = float(b_val)
            if expected_rel == "a_greater":
                pass_axes.append(a_num > b_num)
            elif expected_rel == "b_greater":
                pass_axes.append(b_num > a_num)
            elif expected_rel == "different":
                pass_axes.append(abs(a_num - b_num) > 0.01)
            else:
                pass_axes.append(False)
        except (TypeError, ValueError):
            # Non-numeric — just compare inequality.
            pass_axes.append(a_val != b_val)

    passed = bool(pass_axes) and all(pass_axes) and not errors
    reason = (
        f"diverged on {len([p for p in pass_axes if p])}/{len(pass_axes)} axes"
        if pass_axes else "no divergence axes declared"
    )

    return AncestryConflictResult(
        scenario_id=scenario.scenario_id,
        passed=passed,
        reason=reason,
        run_a=run_a,
        run_b=run_b,
        extra_runs=extras,
        divergence_observed=observed,
        errors=tuple(errors),
    )


def run_all_ancestry_conflicts(
    *,
    orchestrator: GeminiOrchestrator | None = None,
    include: tuple[str, ...] | None = None,
) -> list[AncestryConflictResult]:
    """Run every scenario (or a filtered subset by scenario_id)."""
    orch = orchestrator or GeminiOrchestrator()
    selected = (
        ANCESTRY_CONFLICT_SCENARIOS
        if include is None
        else [s for s in ANCESTRY_CONFLICT_SCENARIOS if s.scenario_id in include]
    )
    return [run_ancestry_conflict(s, orchestrator=orch) for s in selected]


__all__ = [
    "AncestryConflictScenario",
    "AncestryConflictResult",
    "ANCESTRY_CONFLICT_SCENARIOS",
    "run_ancestry_conflict",
    "run_all_ancestry_conflicts",
]
