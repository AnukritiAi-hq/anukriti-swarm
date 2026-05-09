"""Anukriti Swarm — Unified Execution Demo (SwarmRuntime-backed).

Closes phase 2 of the Unified Orchestration + Visualization brief.

The demo body now delegates to ``SwarmRuntime`` (phase 2, commit 5)
instead of composing free stage functions. Every stage, every
event, every report field lives on the runtime class — the demo
is just a 3-scenario driver with a side-by-side scorecard.

When the FastAPI backend (phase 3) exposes a WebSocket endpoint,
the same SwarmRuntime will be used server-side and clients will
see live events as the lifecycle progresses.

Run:
    python -m demos.unified_demo
"""

from __future__ import annotations

from core.models.population import SuperPopulation
from core.runtime import (
    SwarmRuntime,
    UnifiedExecutionContext,
    UnifiedExecutionReport,
)


# ---------------------------------------------------------------------------
# ANSI formatting (matches sibling demos)
# ---------------------------------------------------------------------------


B, D, R = "\033[1m", "\033[2m", "\033[0m"
CYAN, GREEN, YELLOW, RED, MAGENTA, BLUE = (
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
    "\033[35m",
    "\033[34m",
)


def _banner(title: str, subtitle: str = "") -> None:
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  {title}{R}")
    print(f"  {B}{'═' * 68}{R}")
    if subtitle:
        print(f"  {D}  {subtitle}{R}")


def _scenario(title: str, subtitle: str = "") -> None:
    print(f"\n  {B}{BLUE}  {title}{R}")
    print(f"  {B}{'─' * 68}{R}")
    if subtitle:
        print(f"  {D}  {subtitle}{R}")


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


SCENARIOS = [
    {
        "title": "Clopidogrel + CYP2C19 + South Asian",
        "subtitle": "36% SAS carry CYP2C19*2 (loss-of-function) — use prasugrel/ticagrelor.",
        "drug": "clopidogrel", "gene": "CYP2C19",
        "population": SuperPopulation.SAS, "genotype": "*2/*2",
    },
    {
        "title": "Carbamazepine + HLA-B*15:02 + East Asian",
        "subtitle": "HLA-B*15:02 carriers at 8% EAS prevalence — CBZ contraindicated.",
        "drug": "carbamazepine", "gene": "HLA-B",
        "population": SuperPopulation.EAS, "genotype": "*15:02/positive",
    },
    {
        "title": "Codeine + CYP2D6 + African ancestry",
        "subtitle": "CYP2D6*4 PM in AFR — seed lacks AFR-specific evidence.",
        "drug": "codeine", "gene": "CYP2D6",
        "population": SuperPopulation.AFR, "genotype": "*4/*4",
    },
]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render(report: UnifiedExecutionReport, event_count: int) -> None:
    rec = report.final_recommendation
    ev = report.evidence_sufficiency or {}
    unc = report.uncertainty_analysis or {}

    gate = f"{GREEN}✓ synthesis{R}" if rec["allows_synthesis"] else f"{RED}✗ refused{R}"
    print(f"  {B}agents:{R} {D}{', '.join(report.activated_agents)}{R}")
    print(f"  {B}graph paths:{R} {len(report.graph_traversal)} · "
          f"{B}rules:{R} {len(report.deterministic_rules)} · "
          f"{B}events:{R} {event_count}")
    print(f"  {B}decision:{R} {ev.get('sufficiency_decision','?')}  "
          f"{B}verdict:{R} {ev.get('verdict','?')}  "
          f"{B}uncertainty:{R} {unc.get('uncertainty_score','?')}  {gate}")
    if rec["allows_synthesis"]:
        print(f"  {B}recommendation:{R} {D}{rec['text'][:72]}{'...' if len(rec['text']) > 72 else ''}{R}")
    else:
        print(f"  {B}blocking:{R} {D}{rec['blocking_reason'][:90]}{R}")
    print(f"  {B}duration:{R} {report.total_duration_ms:.2f}ms")


def main() -> None:
    _banner(
        "🧬 ANUKRITI SWARM — Unified Execution (SwarmRuntime)",
        "single lifecycle class · 3 scenarios · streamable events · 1 report each"
    )

    # One SwarmRuntime instance handles all three scenarios — shared
    # components are built once and reused.
    runtime = SwarmRuntime()

    reports: list[UnifiedExecutionReport] = []
    event_counts: list[int] = []
    events_before = 0

    for scenario in SCENARIOS:
        _scenario(scenario["title"], scenario["subtitle"])
        ctx = UnifiedExecutionContext.new(
            drug=scenario["drug"], gene=scenario["gene"],
            population=scenario["population"], genotype=scenario["genotype"],
        )
        report = runtime.run(ctx)
        events_emitted = len(runtime.event_stream.events) - events_before
        events_before = len(runtime.event_stream.events)
        _render(report, events_emitted)
        reports.append(report)
        event_counts.append(events_emitted)

    # -------- Side-by-side scorecard --------
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  📋 UNIFIED SCORECARD{R}")
    print(f"  {B}{'═' * 68}{R}")
    print(f"  {B}{'Scenario':42} {'Decision':14} {'Verdict':11} "
          f"{'Uncert.':9} {'Events':7} Gate{R}")
    print(f"  {B}{'─' * 108}{R}")
    for sc, rep, n_events in zip(SCENARIOS, reports, event_counts):
        ev = rep.evidence_sufficiency or {}
        unc = rep.uncertainty_analysis or {}
        gate = f"{GREEN}✓{R}" if rep.final_recommendation["allows_synthesis"] else f"{RED}✗{R}"
        print(f"  {sc['title'][:42]:42} "
              f"{ev.get('sufficiency_decision','?')[:14]:14} "
              f"{ev.get('verdict','?')[:11]:11} "
              f"{unc.get('uncertainty_score','?')[:9]:9} "
              f"{n_events:^7} {gate}")

    total_events = len(runtime.event_stream.events)
    print(f"\n  {D}Total RuntimeEvents across all runs: {total_events}{R}")
    print(f"  {D}One SwarmRuntime instance; components built once; reused across scenarios.{R}")

    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  Unified orchestration · deterministic core · streamable events{R}")
    print(f"  {B}{CYAN}  Evidence-governed genomic intelligence infrastructure.{R}")
    print(f"  {B}{'═' * 68}{R}\n")


if __name__ == "__main__":
    main()
