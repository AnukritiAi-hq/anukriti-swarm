"""Anukriti Swarm — CLI Analysis Runner.

Command-line interface for running pharmacogenomic analyses.

Usage:
  python -m scripts.run_analysis --gene CYP2C19 --drug clopidogrel --population SAS --alleles "*1/*2"
  python -m scripts.run_analysis --gene CYP2D6 --drug codeine --population EUR --alleles "*4/*4"
"""

from __future__ import annotations

import argparse
import json
import sys

from workflows.pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Anukriti Swarm — Pharmacogenomic Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example: python -m scripts.run_analysis --gene CYP2C19 --drug clopidogrel --population SAS --alleles '*1/*2'",
    )
    parser.add_argument("--gene", required=True, help="Gene symbol (e.g., CYP2C19, CYP2D6)")
    parser.add_argument("--drug", required=True, help="Drug name (e.g., clopidogrel, codeine)")
    parser.add_argument("--population", required=True, help="Population code (SAS, EUR, AFR)")
    parser.add_argument("--alleles", required=True, help="Diplotype (e.g., '*1/*2')")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--verbose", action="store_true", help="Show execution trace")

    args = parser.parse_args()

    # Parse alleles
    alleles = args.alleles.replace("'", "").replace('"', "").split("/")
    if len(alleles) != 2:
        print(f"Error: --alleles must be in format '*1/*2', got '{args.alleles}'", file=sys.stderr)
        sys.exit(1)

    # Build initial state
    state = {
        "gene": args.gene,
        "drug": args.drug,
        "population": args.population,
        "allele1": alleles[0],
        "allele2": alleles[1],
    }

    # Run pipeline
    result, trace = run_pipeline(state)

    # Output
    if args.format == "json":
        output = {
            "gene": result.get("gene"),
            "diplotype": result.get("diplotype"),
            "drug": result.get("drug"),
            "population": result.get("population"),
            "pharmacogene_result": result.get("pharmacogene_result"),
            "population_result": result.get("population_result"),
            "recommendations": result.get("recommendations"),
            "verification": result.get("verification"),
            "citations": result.get("citations"),
            "trace": {
                "correlation_id": trace.correlation_id,
                "total_ms": round(trace.total_duration_ms, 1),
                "stages": len(trace.stages),
            },
        }
        print(json.dumps(output, indent=2, default=str))
    else:
        if args.verbose:
            print(trace.summary())
            print()
        print(result.get("narrative", "[No narrative generated]"))


if __name__ == "__main__":
    main()
