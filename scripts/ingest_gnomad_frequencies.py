#!/usr/bin/env python3
"""Offline ingestion: real gnomAD v2.1.1 exomes allele frequencies via BigQuery.

Queries bigquery-public-data.gnomAD exomes tables by rsID for the PGx
defining variants, maps subpops -> Anukriti superpops, and writes a pinned
JSONL artifact (datasets/pharmfreq/gnomad_v2_1_1_frequencies.jsonl) in the
AlleleFrequencyRecord schema. Offline: run once, commit the artifact. The
reasoning path never touches BigQuery.

Usage:
    python scripts/ingest_gnomad_frequencies.py --project <gcp-project>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from datasets.pharmfreq.pgx_variant_map import GNOMAD_POP_MAP, PGX_VARIANTS

DATASET = "bigquery-public-data.gnomAD"
SOURCE = "gnomAD"
VERSION = "v2.1.1_exomes_bigquery"
OUT = Path(__file__).resolve().parent.parent / "datasets" / "pharmfreq" / "gnomad_v2_1_1_frequencies.jsonl"

# rsID -> exomes chromosome table suffix (gene loci)
RSID_CHR = {
    "rs3892097": "22", "rs1065852": "22", "rs28371706": "22",
    "rs4244285": "10", "rs4986893": "10", "rs12248560": "10",
    "rs1799853": "10", "rs1057910": "10",
    "rs4149056": "12", "rs9923231": "16",
    "rs1800462": "6", "rs1800460": "6", "rs1142345": "6",
    "rs3918290": "1", "rs67376798": "1", "rs56038477": "1",
    "rs1801280": "8", "rs1799930": "8", "rs1799931": "8",
    "rs3745274": "19", "rs762551": "15", "rs776746": "7",
    "rs1050828": "X", "rs5030868": "X",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    args = ap.parse_args()

    from google.cloud import bigquery

    client = bigquery.Client(project=args.project)

    # group rsIDs by chromosome to query each exomes table once
    by_chr: dict[str, list[str]] = {}
    for rsid, ch in RSID_CHR.items():
        by_chr.setdefault(ch, []).append(rsid)

    records: list[dict] = []

    def pull(kind: str, ch: str, rsids: list[str], version: str) -> set[str]:
        """Query one gnomAD table; append records; return rsIDs found."""
        # genomes v2.1.1 has no SAS ancestry
        subpops = [p for p in GNOMAD_POP_MAP if not (kind == "genomes" and p == "sas")]
        afc = ", ".join(f"ab.AF_{p} AS af_{p}" for p in subpops)
        anc = ", ".join(f"AN_{p} AS an_{p}" for p in subpops)
        ids = ", ".join(f"'{r}'" for r in rsids)
        q = f"""
        SELECT (SELECT n FROM UNNEST(names) n WHERE n LIKE 'rs%' LIMIT 1) AS rsid,
               {afc}, {anc}
        FROM `{DATASET}.v2_1_1_{kind}__chr{ch}`, UNNEST(alternate_bases) AS ab
        WHERE EXISTS (SELECT 1 FROM UNNEST(names) n WHERE n IN ({ids}))
        """
        found: set[str] = set()
        for row in client.query(q).result():
            rsid = row["rsid"]
            if rsid not in PGX_VARIANTS:
                continue
            found.add(rsid)
            gene, allele, function = PGX_VARIANTS[rsid]
            for sub in subpops:
                af, an = row[f"af_{sub}"], row[f"an_{sub}"]
                if af is None or not an:
                    continue
                records.append({
                    "gene": gene, "allele": allele, "population": GNOMAD_POP_MAP[sub],
                    "frequency": round(float(af), 6), "sample_n": an // 2,
                    "source": SOURCE, "version": version, "function": function,
                    "rsid": rsid,
                })
        return found

    found: set[str] = set()
    for ch, rsids in sorted(by_chr.items()):
        found |= pull("exomes", ch, rsids, VERSION)

    # genomes fallback for regulatory/intronic variants absent from exomes (no SAS)
    missing_by_chr: dict[str, list[str]] = {}
    for rsid in set(PGX_VARIANTS) - found:
        missing_by_chr.setdefault(RSID_CHR[rsid], []).append(rsid)
    for ch, rsids in sorted(missing_by_chr.items()):
        pull("genomes", ch, rsids, "v2.1.1_genomes_bigquery")

    OUT.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    print(f"wrote {len(records)} records -> {OUT}")


if __name__ == "__main__":
    main()
