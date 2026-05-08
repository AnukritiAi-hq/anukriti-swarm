"""Demo — Gemini-powered orchestration framework.

Run::

    python -m demos.gemini_orchestrator_demo

Shows the three public entry points of ``GeminiOrchestrator``:

1. ``run`` — single query (CYP2C19 *2/*2 + clopidogrel in SAS)
2. ``compare_populations`` — same genotype across SAS / AFR / EUR
3. ``compare_drugs`` — same genotype across clopidogrel / omeprazole

For each scenario the demo prints:

- The orchestration summary (phase, verification, trace sizes)
- The orchestration trace (per-step origin + duration)
- The generated narratives (audit + comparative where applicable)
- The conflict resolution tier + any detected conflicts

The demo works **without** API access — when neither ``OPENAI_API_KEY``
nor ``GEMINI_API_KEY`` is present the planner falls back to the
deterministic path, and the coordinator's synthesis step falls back
to the ``AIClient._build_fallback`` templated text. Both fallbacks are
explicitly visible in the trace (``origin=deterministic`` on the plan
step, ``model=… (fallback)`` on the narrative steps).

The deterministic biomedical pipeline is the same one used by the
existing ``demos.showcase`` and ``demos.flagship`` — this demo wraps
it in the new orchestration layer.
"""

from __future__ import annotations

import os
import sys

from agents.orchestrator import GeminiOrchestrator, OrchestrationResult


BAR = "=" * 78


def _banner(title: str) -> None:
    print()
    print(BAR)
    print(f"  {title}")
    print(BAR)


def _render_result(result: OrchestrationResult, show_comparison: bool = False) -> None:
    """Pretty-print one OrchestrationResult."""
    print(result.summary())

    # Trace
    print()
    print("--- Orchestration Trace ---")
    print(result.trace.summary())

    # Conflict resolution
    resolution = result.coordination.resolution
    print()
    print("--- Conflict Resolution ---")
    if resolution is None:
        print("  (resolver did not run — run escalated before it)")
    else:
        print(f"  tier: {resolution.tier.value}")
        if resolution.conflicts:
            for c in resolution.conflicts:
                print(f"    [{c.tier.value}] {c.kind.value}: {c.message}")
        else:
            print("  no conflicts")

    # Escalation
    if result.escalated:
        print()
        print("--- Escalation ---")
        print(f"  reason: {result.coordination.escalation_reason}")

    # Narratives
    if result.narratives:
        print()
        print("--- Narratives ---")
        for audience, text in result.narratives.items():
            print(f"  [{audience}]")
            for line in text.splitlines() or [text]:
                print(f"    {line}")
            print()

    # Comparison rows (only for comparative runs)
    if show_comparison and result.comparison_rows:
        print("--- Comparison rows (deterministic, Gemini narrates from these) ---")
        for row in result.comparison_rows:
            print(
                f"  {row['label']:<14} phenotype={row['phenotype']:<18} "
                f"risk={row['risk']:<10} freq={row['frequency']} "
                f"rec={row['recommendation']}"
            )


def _provider_banner() -> None:
    """Tell the user which provider (if any) will be used."""
    if os.environ.get("OPENAI_API_KEY"):
        print("AI provider: OpenAI (live narrative generation)")
    elif os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        print("AI provider: Gemini (live narrative generation)")
    else:
        print("AI provider: none — all generative steps will use deterministic")
        print("fallbacks. Set OPENAI_API_KEY or GEMINI_API_KEY for live narration.")


def main() -> int:
    _banner("Anukriti Swarm — Gemini Orchestration Demo")
    _provider_banner()

    orchestrator = GeminiOrchestrator()

    # ------------------------------------------------------------------
    # Scenario 1 — single-query run
    # ------------------------------------------------------------------
    _banner("Scenario 1 — single query (CYP2C19 *2/*2 + clopidogrel in SAS)")
    r1 = orchestrator.run(
        gene="CYP2C19",
        drug="clopidogrel",
        population="SAS",
        allele1="*2",
        allele2="*2",
    )
    _render_result(r1)

    # ------------------------------------------------------------------
    # Scenario 2 — multi-population fan-out
    # ------------------------------------------------------------------
    _banner("Scenario 2 — compare_populations (SAS / AFR / EUR)")
    r2 = orchestrator.compare_populations(
        gene="CYP2C19",
        drug="clopidogrel",
        populations=["SAS", "AFR", "EUR"],
        allele1="*2",
        allele2="*2",
    )
    _render_result(r2, show_comparison=True)

    # ------------------------------------------------------------------
    # Scenario 3 — multi-drug fan-out
    # ------------------------------------------------------------------
    _banner("Scenario 3 — compare_drugs (clopidogrel / omeprazole)")
    r3 = orchestrator.compare_drugs(
        gene="CYP2C19",
        drugs=["clopidogrel", "omeprazole"],
        population="SAS",
        allele1="*2",
        allele2="*2",
    )
    _render_result(r3, show_comparison=True)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    _banner("Demo complete")
    for label, r in (("run", r1), ("compare_populations", r2), ("compare_drugs", r3)):
        verdict = r.verification_state.value
        runs = len(r.coordination.runs)
        narratives = ",".join(r.narratives.keys()) or "—"
        escalated = " ESCALATED" if r.escalated else ""
        print(
            f"  {label:<22} runs={runs} verify={verdict} "
            f"narratives={narratives} total={r.total_duration_ms:.1f}ms"
            f"{escalated}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
