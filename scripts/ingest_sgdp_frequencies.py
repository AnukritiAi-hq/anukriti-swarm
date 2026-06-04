#!/usr/bin/env python3
"""Offline ingestion: SGDP per-population allele frequencies via BigQuery.

Computes per-superpopulation allele frequencies for the PGx defining
variants from the Simons Genome Diversity Project (278 samples, 127
populations) public BigQuery tables, by counting ALT alleles in the
per-sample genotype calls joined to sample-region metadata.

SGDP has no precomputed AF, so frequency = ALT allele count / called
alleles, per superpopulation. Single ~41 GB scan (under the 1 TB/month
free tier). Writes datasets/pharmfreq/sgdp_frequencies.jsonl. Offline:
run once, commit the artifact; the reasoning path never touches BigQuery.

Usage:
    python scripts/ingest_sgdp_frequencies.py --project <gcp-project>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from datasets.pharmfreq.pgx_variant_map import PGX_VARIANTS

P = "bigquery-public-data.human_genome_variants"
VARIANTS = f"{P}.simons_genome_diversity_project_sample_variants"
ATTRS = f"{P}.simons_genome_diversity_project_sample_attributes"
SOURCE = "SGDP"
VERSION = "v1_bigquery"
OUT = Path(__file__).resolve().parent.parent / "datasets" / "pharmfreq" / "sgdp_frequencies.jsonl"

# SGDP region -> Anukriti superpopulation
REGION_MAP = {
    "Africa": "AFR",
    "America": "AMR",
    "EastAsia": "EAS",
    "SouthAsia": "SAS",
    "WestEurasia": "EUR",
    # CentralAsiaSiberia + Oceania have no Anukriti superpop; dropped honestly.
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()

    from google.cloud import bigquery

    client = bigquery.Client(project=args.project)
    ids = ", ".join(f"'{r}'" for r in PGX_VARIANTS)
    regions = ", ".join(f"'{r}'" for r in REGION_MAP)

    # SGDP variants table stores only non-reference calls; samples absent at
    # a site are homozygous reference. So AF = ALT alleles observed /
    # (2 * total samples in the region). Single scan over the variants table.
    q = f"""
    WITH region_n AS (
      SELECT region, COUNT(*) AS n
      FROM `{ATTRS}` WHERE region IN ({regions}) GROUP BY region
    ),
    samp AS (
      SELECT id_from_vcf, region FROM `{ATTRS}` WHERE region IN ({regions})
    ),
    alt_counts AS (
      SELECT (SELECT n FROM UNNEST(v.names) n WHERE n LIKE 'rs%' LIMIT 1) AS rsid,
             s.region AS region,
             SUM((SELECT COUNT(*) FROM UNNEST(call.genotype) g WHERE g > 0)) AS alt
      FROM `{VARIANTS}` v, UNNEST(v.call) call
      JOIN samp s ON call.name = s.id_from_vcf
      WHERE EXISTS (SELECT 1 FROM UNNEST(v.names) n WHERE n IN ({ids}))
      GROUP BY rsid, region
    )
    SELECT a.rsid, a.region, a.alt, rn.n AS samples
    FROM alt_counts a JOIN region_n rn ON a.region = rn.region
    """

    records: list[dict] = []
    for row in client.query(q).result():
        rsid, region = row["rsid"], row["region"]
        if rsid not in PGX_VARIANTS or not row["samples"]:
            continue
        gene, allele, function = PGX_VARIANTS[rsid]
        records.append({
            "gene": gene, "allele": allele, "population": REGION_MAP[region],
            "frequency": round(row["alt"] / (2 * row["samples"]), 6),
            "sample_n": row["samples"],
            "source": SOURCE, "version": VERSION, "function": function,
            "rsid": rsid,
        })

    OUT.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    print(f"wrote {len(records)} records -> {OUT}")


if __name__ == "__main__":
    main()
