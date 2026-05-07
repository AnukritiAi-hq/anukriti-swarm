"""Anukriti Swarm — Biomedical Data Integration Demo.

Demonstrates the structured data layer:
- Gene metadata lookup
- Allele definitions with provenance
- Population prevalence comparison
- Guideline recommendations
- Full provenance trail

Run: python -m demos.biomedical_data_demo
"""

from __future__ import annotations

from data.lookup import BiomedicalLookup


def run_demo() -> None:
    print("=" * 70)
    print("🧬 ANUKRITI SWARM — Biomedical Data Integration")
    print("   Deterministic. Provenance-tracked. Auditable.")
    print("=" * 70)

    api = BiomedicalLookup()

    # --- Gene Metadata ---
    print("\n" + "─" * 70)
    print("1. GENE METADATA")
    print("─" * 70)

    for symbol in ["CYP2D6", "CYP2C19", "HLA-B"]:
        r = api.gene(symbol)
        g = r.data
        print(f"\n  {g.symbol} ({g.chromosome})")
        print(f"    Function: {g.function}")
        print(f"    Key drugs: {', '.join(g.key_drugs[:4])}")
        print(f"    Significance: {g.clinical_significance}")
        print(f"    Source: {r.provenance.source.value} {r.provenance.version}")

    # --- Allele Definitions ---
    print("\n" + "─" * 70)
    print("2. CYP2D6 ALLELE DEFINITIONS")
    print("─" * 70)

    r = api.alleles("CYP2D6")
    print(f"\n  {'Allele':<8} {'Function':<22} {'Score':<6} {'Variants'}")
    print(f"  {'─'*8} {'─'*22} {'─'*6} {'─'*20}")
    for a in r.data:
        variants = ", ".join(a.defining_variants) or "—"
        print(f"  {a.allele:<8} {a.function_status:<22} {a.activity_score:<6.1f} {variants}")

    # --- Population Prevalence Comparison ---
    print("\n" + "─" * 70)
    print("3. CYP2C19 METABOLIZER PREVALENCE BY POPULATION")
    print("─" * 70)

    for pop in ["SAS", "AFR", "EUR"]:
        r = api.prevalence("CYP2C19", pop)
        print(f"\n  {pop} (n={r.data[0].sample_n:,}):")
        for rec in r.data:
            bar = "█" * int(rec.prevalence * 40)
            print(f"    {rec.phenotype:>3}: {rec.prevalence:>5.1%} {bar}")

    # --- HLA-B*15:02 Carrier Rates ---
    print("\n" + "─" * 70)
    print("4. HLA-B*15:02 CARRIER PREVALENCE")
    print("─" * 70)

    for pop in ["SAS", "AFR", "EUR", "EAS"]:
        r = api.prevalence("HLA-B", pop)
        if r.found:
            rec = r.data[0]
            bar = "█" * int(rec.prevalence * 100)
            print(f"  {pop}: {rec.prevalence:>5.1%} {bar} (n={rec.sample_n:,})")

    # --- Guideline Lookup ---
    print("\n" + "─" * 70)
    print("5. CPIC GUIDELINE LOOKUP")
    print("─" * 70)

    queries = [
        ("CYP2C19", "Poor Metabolizer", "clopidogrel"),
        ("CYP2D6", "Poor Metabolizer", "codeine"),
        ("HLA-B", "HLA-B*15:02 positive", "carbamazepine"),
    ]
    for gene, pheno, drug in queries:
        r = api.guideline(gene, pheno, drug)
        if r.found:
            g = r.data
            print(f"\n  {gene} / {pheno} / {drug}:")
            print(f"    [{g.strength:>8}] {g.recommendation}")
            print(f"    Source: {g.guideline_id} ({g.pmid})")

    # --- Provenance ---
    print("\n" + "─" * 70)
    print("6. PROVENANCE TRAIL")
    print("─" * 70)

    r = api.allele("CYP2D6", "*4")
    print(f"\n  Query: {r.query}")
    print(f"  Found: {r.found}")
    print(f"  Confidence: {r.confidence}")
    print(f"  Source: {r.provenance.source.value} {r.provenance.version}")
    print(f"  Accessed: {r.timestamp.isoformat()}")
    print(f"  License: {r.provenance.license}")

    print(f"\n{'=' * 70}")
    print("✅ All data deterministic, versioned, and provenance-tracked.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
