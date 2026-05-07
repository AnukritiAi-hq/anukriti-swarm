"""Anukriti Swarm — Narrative Report Demo.

Generates a compelling CYP2C19/clopidogrel/South Asian report
in all three audience formats: patient, researcher, audit.

Run: python -m demos.narrative_report_demo
"""

from __future__ import annotations

from narrative.engine import Audience, NarrativeEngine
from reports.generator import to_json, to_markdown
from workflows.pipeline import run_pipeline


def run_demo() -> None:
    print("=" * 70)
    print("🧬 ANUKRITI SWARM — Narrative Report Engine Demo")
    print("   Three audiences. One truth. Full provenance.")
    print("=" * 70)

    # Run pipeline to get state
    state, trace = run_pipeline({
        "gene": "CYP2C19",
        "drug": "clopidogrel",
        "population": "SAS",
        "allele1": "*2",
        "allele2": "*2",
    })

    engine = NarrativeEngine()

    # --- Patient Report ---
    print("\n" + "═" * 70)
    print("  📋 PATIENT REPORT")
    print("═" * 70)

    patient_report = engine.generate(state, Audience.PATIENT)
    print(to_markdown(patient_report))

    # --- Researcher Report ---
    print("\n" + "═" * 70)
    print("  🔬 RESEARCHER REPORT")
    print("═" * 70)

    researcher_report = engine.generate(state, Audience.RESEARCHER)
    print(to_markdown(researcher_report))

    # --- Audit Report ---
    print("\n" + "═" * 70)
    print("  📊 AUDIT REPORT")
    print("═" * 70)

    audit_report = engine.generate(state, Audience.AUDIT)
    print(to_markdown(audit_report))

    # --- JSON Export ---
    print("\n" + "═" * 70)
    print("  📦 JSON EXPORT (researcher)")
    print("═" * 70)

    json_output = to_json(researcher_report)
    # Show just metadata section
    import json
    data = json.loads(json_output)
    print(f"\n  Sections: {data['metadata']['total_sections']}")
    print(f"  Deterministic: {data['metadata']['deterministic_sections']}")
    print(f"  Narrative: {data['metadata']['narrative_sections']}")
    print(f"  Citations: {', '.join(data['metadata']['all_citations'])}")
    print(f"  JSON size: {len(json_output)} bytes")

    # --- Summary ---
    print(f"\n{'=' * 70}")
    print("  ✅ Three reports generated from one pipeline execution.")
    print("     Every claim cited. Every interpretation traceable.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
