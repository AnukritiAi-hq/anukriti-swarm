"""Anukriti Swarm — Observability & Introspection Demo.

Demonstrates the full observability stack:
- Execution metrics collection
- CLI dashboard rendering
- Structured telemetry export
- Execution replay format
- Multi-execution summary

Run: python -m demos.observability_demo
"""

from __future__ import annotations

from dashboards.cli_dashboard import render_dashboard, render_summary_table
from metrics.collector import MetricsCollector
from tracing.telemetry import TelemetryExporter
from workflows.pipeline import run_pipeline


def run_demo() -> None:
    print("=" * 70)
    print("🧬 ANUKRITI SWARM — Observability & Introspection Demo")
    print("   Transparent. Traceable. Intelligent infrastructure.")
    print("=" * 70)

    collector = MetricsCollector()
    exporter = TelemetryExporter()

    # Run multiple scenarios
    scenarios = [
        {"gene": "CYP2C19", "drug": "clopidogrel", "population": "SAS", "allele1": "*2", "allele2": "*2"},
        {"gene": "CYP2D6", "drug": "codeine", "population": "EUR", "allele1": "*1", "allele2": "*4"},
        {"gene": "CYP2C19", "drug": "clopidogrel", "population": "AFR", "allele1": "*1", "allele2": "*2"},
    ]

    states = []
    for scenario in scenarios:
        state, trace = run_pipeline(scenario)
        metrics = collector.collect(state, trace)
        states.append((state, trace, metrics))

    # --- Dashboard for first execution ---
    print("\n" + "─" * 70)
    print("  DASHBOARD: CYP2C19 *2/*2 / clopidogrel / SAS")
    print("─" * 70)

    state, trace, metrics = states[0]
    print(render_dashboard(metrics, state))

    # --- Telemetry spans ---
    print("─" * 70)
    print("  TELEMETRY: Structured spans (JSONL)")
    print("─" * 70)

    spans = exporter.export_spans(trace, state)
    jsonl = exporter.to_jsonl(spans)
    print(f"\n  Spans exported: {len(spans)}")
    print(f"  Format: JSONL ({len(jsonl)} bytes)")
    print(f"\n  Sample span:")
    for line in jsonl.split("\n")[:2]:
        print(f"    {line[:90]}...")

    # --- Replay format ---
    print(f"\n{'─' * 70}")
    print("  REPLAY: Reproducible execution format")
    print("─" * 70)

    replay = exporter.to_replay_format(trace, state)
    print(f"\n  Replay export: {len(replay)} bytes")
    import json
    data = json.loads(replay)
    print(f"  Input: {data['input']}")
    print(f"  Expected: {data['expected_output']}")

    # --- Multi-execution summary ---
    print(f"\n{'─' * 70}")
    print("  HISTORY: Multi-execution summary")
    print("─" * 70)
    print()
    print(render_summary_table(collector.history))

    # --- Aggregate stats ---
    print(f"\n{'─' * 70}")
    print("  AGGREGATE: Cross-execution statistics")
    print("─" * 70)

    summary = collector.summary()
    print(f"\n  Executions:          {summary['executions']}")
    print(f"  Avg Duration:        {summary['avg_duration_ms']:.2f} ms")
    print(f"  Avg Confidence:      {summary['avg_confidence']:.3f}")
    print(f"  Verification Pass:   {summary['verification_pass_rate']:.0%}")
    print(f"  Avg Citations:       {summary['avg_citations']:.1f}")
    print(f"  Avg Grounding:       {summary['avg_grounding']:.0%}")

    print(f"\n{'=' * 70}")
    print("  ✅ Full observability: metrics, telemetry, dashboards, replay.")
    print("     This is intelligent distributed genomic reasoning infrastructure.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
