#!/usr/bin/env python3
"""Offline ingestion: GenomeIndia public aggregate allele frequencies.

Reads the public ``9768GI_SummaryStats.tar.gz`` release, an extracted
directory containing its 22 autosomal TSVs, or a focused JSONL extract with
``gene/chrom/pos/ref/alt/af_indian_9768`` fields, and writes a pinned JSONL
artifact in the ``AlleleFrequencyRecord`` schema:

    datasets/pharmfreq/genomeindia_9768_summary_frequencies.jsonl

The public release described by UCSC contains aggregate Indian AF columns
only: CHROM, POS, ID, REF, ALT, AF. It does not carry the 83-population
breakdown, so records are mapped to Anukriti's SAS bucket with explicit
GenomeIndia provenance rather than represented as community-specific data.

Usage:
    curl -L --max-time 600 -o /tmp/9768GI_SummaryStats.tar.gz \
      'https://ibdc.dbt.gov.in/genomeindia/downloadfile?path=9768GI_SummaryStats.tar.gz'
    python scripts/ingest_genomeindia_frequencies.py /tmp/9768GI_SummaryStats.tar.gz
    python scripts/ingest_genomeindia_frequencies.py /tmp/9768GI_SummaryStats/
    python scripts/ingest_genomeindia_frequencies.py ../17675458c_genomeindia_pgx_variants.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from datasets.pharmfreq.pgx_variant_map import (  # noqa: E402
    GENOMEINDIA_VARIANT_COORDS,
    GENOMEINDIA_VARIANTS,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

SOURCE = "GenomeIndia"
VERSION = "9768GI_SummaryStats_2025_public_aggregate"
SAMPLE_N = 9768
POPULATION = "SAS"
OUT = (
    Path(__file__).resolve().parent.parent
    / "datasets"
    / "pharmfreq"
    / "genomeindia_9768_summary_frequencies.jsonl"
)


@dataclass(frozen=True)
class GenomeIndiaRecord:
    gene: str
    allele: str
    population: str
    frequency: float
    sample_n: int
    source: str
    version: str
    function: str
    rsid: str
    chrom: str
    pos: int
    ref: str
    alt: str


def _iter_tar_lines(path: Path) -> Iterator[str]:
    with tarfile.open(path, "r:*") as tf:
        for member in tf:
            if not member.isfile():
                continue
            handle = tf.extractfile(member)
            if handle is None:
                continue
            for raw in handle:
                yield raw.decode("utf-8", errors="replace")


def _iter_text_lines(path: Path) -> Iterator[str]:
    yield from path.read_text(encoding="utf-8", errors="replace").splitlines()


def _iter_dir_lines(path: Path) -> Iterator[str]:
    for file_path in sorted(path.rglob("*")):
        if file_path.is_file():
            yield from _iter_text_lines(file_path)


def _iter_rows(source: Path) -> Iterator[list[str]]:
    if source.is_dir():
        lines: Iterable[str] = _iter_dir_lines(source)
    elif source.suffix == ".jsonl":
        lines = _iter_text_lines(source)
    else:
        lines = _iter_tar_lines(source)

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("{"):
            row = json.loads(line)
            chrom = str(row["chrom"]).removeprefix("chr")
            yield [
                chrom,
                str(row["pos"]),
                str(row.get("id") or "."),
                str(row["ref"]),
                str(row["alt"]),
                str(row["af_indian_9768"]),
            ]
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            parts = line.split()
        if len(parts) < 6:
            continue
        if parts[0].lower() in {"chrom", "#chrom"}:
            continue
        yield parts


def records_from_summary_stats(source: Path) -> list[GenomeIndiaRecord]:
    records: list[GenomeIndiaRecord] = []
    seen: set[str] = set()
    wanted = set(GENOMEINDIA_VARIANTS)
    by_coord = {
        coord: rsid for rsid, coord in GENOMEINDIA_VARIANT_COORDS.items()
    }

    for parts in _iter_rows(source):
        chrom, pos, rsid, ref, alt, af = parts[:6]
        chrom = chrom.removeprefix("chr")
        rsid = rsid if rsid in wanted else by_coord.get((chrom, int(pos), ref, alt), "")
        if rsid not in wanted or rsid in seen:
            continue
        gene, allele, function = GENOMEINDIA_VARIANTS[rsid]
        records.append(
            GenomeIndiaRecord(
                gene=gene,
                allele=allele,
                population=POPULATION,
                frequency=round(float(af), 8),
                sample_n=SAMPLE_N,
                source=SOURCE,
                version=VERSION,
                function=function,
                rsid=rsid,
                chrom=chrom,
                pos=int(pos),
                ref=ref,
                alt=alt,
            )
        )
        seen.add(rsid)
        if seen == wanted:
            break

    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path, help="9768GI_SummaryStats.tar.gz or extracted directory")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    records = records_from_summary_stats(args.source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "\n".join(json.dumps(asdict(rec), sort_keys=True) for rec in records) + "\n",
        encoding="utf-8",
    )

    missing = sorted(set(GENOMEINDIA_VARIANTS) - {rec.rsid for rec in records})
    print(f"wrote {len(records)} records -> {args.out}")
    if missing:
        print("missing rsIDs: " + ", ".join(missing))


if __name__ == "__main__":
    main()
