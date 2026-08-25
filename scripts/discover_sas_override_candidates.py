#!/usr/bin/env python3
"""Discover GenomeIndia-driven SAS override candidates.

Joins the public GenomeIndia high-frequency PGx extract against a local
gnomAD frequency extract by GRCh38 coordinate and flags variants where:

    GenomeIndia aggregate Indian AF > 5% and gnomAD EUR/NFE AF < 1%.

The gnomAD input is intentionally local-only. Use a chromosome-sliced gnomAD
VCF, TSV, or JSONL extract with GRCh38 coordinates; this avoids thousands of
rate-limited API calls and keeps the reasoning path reproducible.

Usage:
    python scripts/discover_sas_override_candidates.py \
      --gnomad-eur /path/to/gnomad_eur_pgx.tsv

Input schemas:
    GenomeIndia JSONL:
      gene, chrom, pos, ref, alt, af_indian_9768

    gnomAD TSV/JSONL:
      chrom, pos, ref, alt, af_eur
      chrom, pos, ref, alt, af_nfe
      chrom, pos, ref, alt, AF_non_finnish_european

    gnomAD VCF:
      CHROM POS ID REF ALT QUAL FILTER INFO
      INFO field defaults: AF_eur, AF_EUR, AF_nfe, AF_NFE,
      AF_non_finnish_european. Use --eur-field to override.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
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
    from collections.abc import Iterator, Mapping, Sequence

DEFAULT_HIGHFREQ = (
    REPO_ROOT
    / "datasets"
    / "pharmfreq"
    / "genomeindia_9768_highfreq_candidates.jsonl"
)
DEFAULT_GNOMAD = REPO_ROOT / "datasets" / "pharmfreq" / "gnomad_pgx_nfe_sas_frequencies.jsonl"
DEFAULT_OUT = REPO_ROOT / "datasets" / "pharmfreq" / "sas_override_candidates.jsonl"
DEFAULT_GOLD_OUT = REPO_ROOT / "datasets" / "pharmfreq" / "sas_override_gold_candidates.jsonl"
INDIAN_AF_THRESHOLD = 0.05
EUR_AF_THRESHOLD = 0.01
GOLD_INDIAN_AF_MAX = 0.30
EUR_FIELD_CANDIDATES = (
    "af_eur",
    "AF_eur",
    "AF_EUR",
    "eur_af",
    "EUR_AF",
    "af_nfe",
    "AF_nfe",
    "AF_NFE",
    "AF_non_finnish_european",
    "AF_NON_FINNISH_EUROPEAN",
)

Coord = tuple[str, int, str, str]


@dataclass(frozen=True)
class GenomeIndiaVariant:
    gene: str
    chrom: str
    pos: int
    ref: str
    alt: str
    af_indian: float

    @property
    def coord(self) -> Coord:
        return (self.chrom, self.pos, self.ref, self.alt)


@dataclass(frozen=True)
class SasOverrideCandidate:
    gene: str
    chrom: str
    pos: int
    ref: str
    alt: str
    af_indian_9768: float
    af_nfe_gnomad: float
    af_ratio: float | None
    ac_nfe: int
    an_nfe: int
    rsids: list[str]
    gnomad_status: str
    assembly: str
    override_type: str
    threshold: str


@dataclass(frozen=True)
class GnomadFrequency:
    af_nfe: float
    ac_nfe: int = 0
    an_nfe: int = 0
    rsids: tuple[str, ...] = ()


def _normalize_chrom(chrom: object) -> str:
    return str(chrom).removeprefix("chr").removeprefix("CHR")


def _coord(chrom: object, pos: object, ref: object, alt: object) -> Coord:
    return (_normalize_chrom(chrom), int(pos), str(ref).upper(), str(alt).upper())


def _field(row: Mapping[str, object], *names: str) -> object:
    for name in names:
        if name in row:
            return row[name]
    raise KeyError(f"missing required field; tried {', '.join(names)}")


def _open_text(path: Path) -> Iterator[str]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
            yield from handle
        return
    with path.open(encoding="utf-8", errors="replace") as handle:
        yield from handle


def _first_float(row: Mapping[str, object], keys: Sequence[str]) -> float | None:
    for key in keys:
        if key not in row:
            continue
        raw = row[key]
        if raw in {None, "", "."}:
            continue
        return float(str(raw))
    return None


def _first_int(row: Mapping[str, object], keys: Sequence[str]) -> int:
    for key in keys:
        if key not in row:
            continue
        raw = row[key]
        if raw in {None, "", "."}:
            continue
        return int(float(str(raw)))
    return 0


def _rsids_from_raw(raw: object) -> tuple[str, ...]:
    if isinstance(raw, list):
        return tuple(str(item) for item in raw if str(item).startswith("rs"))
    if raw in {None, "", "."}:
        return ()
    return tuple(part for part in str(raw).replace(";", ",").split(",") if part.startswith("rs"))


def _read_genomeindia_highfreq(path: Path) -> list[GenomeIndiaVariant]:
    variants: list[GenomeIndiaVariant] = []
    for line in _open_text(path):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        row = json.loads(line)
        af_indian = float(row["af_indian_9768"])
        if af_indian <= INDIAN_AF_THRESHOLD:
            continue
        chrom, pos, ref, alt = _coord(row["chrom"], row["pos"], row["ref"], row["alt"])
        variants.append(
            GenomeIndiaVariant(
                gene=str(row["gene"]),
                chrom=chrom,
                pos=pos,
                ref=ref,
                alt=alt,
                af_indian=af_indian,
            )
        )
    return variants


def _parse_info(info: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in info.split(";"):
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        parsed[key] = value
    return parsed


def _select_vcf_af(
    info: Mapping[str, str],
    alt_index: int,
    eur_fields: Sequence[str],
) -> float | None:
    for key in eur_fields:
        value = info.get(key)
        if value in {None, "", "."}:
            continue
        parts = value.split(",")
        if len(parts) == 1:
            return float(parts[0])
        if alt_index < len(parts):
            return float(parts[alt_index])
    return None


def _select_vcf_int(info: Mapping[str, str], alt_index: int, keys: Sequence[str]) -> int:
    for key in keys:
        value = info.get(key)
        if value in {None, "", "."}:
            continue
        parts = value.split(",")
        raw = parts[alt_index] if len(parts) > 1 and alt_index < len(parts) else parts[0]
        return int(float(raw))
    return 0


def _read_gnomad_vcf(path: Path, eur_fields: Sequence[str]) -> dict[Coord, GnomadFrequency]:
    freqs: dict[Coord, GnomadFrequency] = {}
    for line in _open_text(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 8:
            parts = line.split()
        if len(parts) < 8:
            continue
        chrom, pos, _id, ref, alts, _qual, _filter, info_raw = parts[:8]
        info = _parse_info(info_raw)
        for alt_index, alt in enumerate(alts.split(",")):
            af = _select_vcf_af(info, alt_index, eur_fields)
            if af is None:
                continue
            freqs[_coord(chrom, pos, ref, alt)] = GnomadFrequency(
                af_nfe=af,
                ac_nfe=_select_vcf_int(info, alt_index, ("AC_nfe", "AC_NFE", "AC_eur", "AC_EUR")),
                an_nfe=_select_vcf_int(info, alt_index, ("AN_nfe", "AN_NFE", "AN_eur", "AN_EUR")),
                rsids=_rsids_from_raw(_id),
            )
    return freqs


def _read_gnomad_jsonl(path: Path, eur_fields: Sequence[str]) -> dict[Coord, GnomadFrequency]:
    freqs: dict[Coord, GnomadFrequency] = {}
    for line in _open_text(path):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        row = json.loads(line)
        af = _first_float(row, eur_fields)
        if af is None:
            continue
        freqs[
            _coord(
                _field(row, "chrom", "CHROM", "#chrom", "#CHROM"),
                _field(row, "pos", "POS"),
                _field(row, "ref", "REF"),
                _field(row, "alt", "ALT"),
            )
        ] = GnomadFrequency(
            af_nfe=af,
            ac_nfe=_first_int(row, ("ac_nfe", "AC_nfe", "AC_NFE", "ac_eur", "AC_EUR")),
            an_nfe=_first_int(row, ("an_nfe", "AN_nfe", "AN_NFE", "an_eur", "AN_EUR")),
            rsids=_rsids_from_raw(row.get("rsids") or row.get("rsid") or row.get("id")),
        )
    return freqs


def _read_gnomad_tsv(path: Path, eur_fields: Sequence[str]) -> dict[Coord, GnomadFrequency]:
    freqs: dict[Coord, GnomadFrequency] = {}
    lines = [line for line in _open_text(path) if line.strip() and not line.startswith("##")]
    sample = lines[0] if lines else ""
    delimiter = "\t" if "\t" in sample else ","
    reader = csv.DictReader(lines, delimiter=delimiter)
    for row in reader:
        af = _first_float(row, eur_fields)
        if af is None:
            continue
        freqs[
            _coord(
                _field(row, "chrom", "CHROM", "#chrom", "#CHROM"),
                _field(row, "pos", "POS"),
                _field(row, "ref", "REF"),
                _field(row, "alt", "ALT"),
            )
        ] = GnomadFrequency(
            af_nfe=af,
            ac_nfe=_first_int(row, ("ac_nfe", "AC_nfe", "AC_NFE", "ac_eur", "AC_EUR")),
            an_nfe=_first_int(row, ("an_nfe", "AN_nfe", "AN_NFE", "an_eur", "AN_EUR")),
            rsids=_rsids_from_raw(row.get("rsids") or row.get("rsid") or row.get("id")),
        )
    return freqs


def read_gnomad_frequencies(path: Path, eur_field: str | None = None) -> dict[Coord, GnomadFrequency]:
    eur_fields = (eur_field,) if eur_field else EUR_FIELD_CANDIDATES
    suffixes = "".join(path.suffixes)
    if suffixes.endswith(".vcf") or suffixes.endswith(".vcf.gz"):
        return _read_gnomad_vcf(path, eur_fields)
    first_line = next((line.lstrip() for line in _open_text(path) if line.strip()), "")
    if (
        suffixes.endswith(".jsonl")
        or suffixes.endswith(".jsonl.gz")
        or first_line.startswith("{")
    ):
        return _read_gnomad_jsonl(path, eur_fields)
    return _read_gnomad_tsv(path, eur_fields)


def discover_candidates(
    highfreq_path: Path,
    gnomad_path: Path,
    eur_field: str | None = None,
) -> list[SasOverrideCandidate]:
    variants = _read_genomeindia_highfreq(highfreq_path)
    gnomad = read_gnomad_frequencies(gnomad_path, eur_field)
    candidates: list[SasOverrideCandidate] = []

    for variant in variants:
        gnomad_freq = gnomad.get(variant.coord)
        if gnomad_freq is None:
            gnomad_freq = GnomadFrequency(af_nfe=0.0)
            gnomad_status = "not_in_gnomad"
        else:
            gnomad_status = "in_gnomad"
        if gnomad_freq.af_nfe >= EUR_AF_THRESHOLD:
            continue

        rsids = list(gnomad_freq.rsids)
        known_rsid = next(
            (
                rsid
                for rsid, coord in GENOMEINDIA_VARIANT_COORDS.items()
                if coord == variant.coord and rsid not in rsids
            ),
            None,
        )
        if known_rsid is not None and known_rsid in GENOMEINDIA_VARIANTS:
            rsids.append(known_rsid)

        af_ratio = (
            None
            if gnomad_freq.af_nfe == 0
            else round(variant.af_indian / gnomad_freq.af_nfe, 2)
        )
        candidates.append(
            SasOverrideCandidate(
                gene=variant.gene,
                chrom=f"chr{variant.chrom}",
                pos=variant.pos,
                ref=variant.ref,
                alt=variant.alt,
                af_indian_9768=round(variant.af_indian, 8),
                af_nfe_gnomad=round(gnomad_freq.af_nfe, 8),
                af_ratio=af_ratio,
                ac_nfe=gnomad_freq.ac_nfe,
                an_nfe=gnomad_freq.an_nfe,
                rsids=rsids,
                gnomad_status=gnomad_status,
                assembly="GRCh38",
                override_type="sas_enriched_eur_rare",
                threshold="indian_af>5% AND nfe_af<1%",
            )
        )

    candidates.sort(
        key=lambda item: (
            item.gnomad_status == "not_in_gnomad",
            float("inf") if item.af_ratio is None else item.af_ratio,
            item.af_indian_9768,
        ),
        reverse=True,
    )
    return candidates


def gold_candidates(candidates: Sequence[SasOverrideCandidate]) -> list[SasOverrideCandidate]:
    return [
        candidate
        for candidate in candidates
        if candidate.rsids
        and candidate.gnomad_status == "in_gnomad"
        and INDIAN_AF_THRESHOLD < candidate.af_indian_9768 <= GOLD_INDIAN_AF_MAX
    ]


def _write_jsonl(path: Path, rows: Sequence[SasOverrideCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(asdict(row), sort_keys=True) for row in rows)
        + ("\n" if rows else ""),
        encoding="utf-8",
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--highfreq", type=Path, default=DEFAULT_HIGHFREQ)
    ap.add_argument("--gnomad-eur", type=Path, default=DEFAULT_GNOMAD)
    ap.add_argument("--eur-field", help="Exact gnomAD TSV/JSONL/VCF EUR AF field to use")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument(
        "--gold-out",
        type=Path,
        default=DEFAULT_GOLD_OUT,
        help="Optional ranked rsID-backed, 5-30%% Indian AF candidate output",
    )
    args = ap.parse_args()

    candidates = discover_candidates(
        args.highfreq,
        args.gnomad_eur,
        args.eur_field,
    )
    gold = gold_candidates(candidates)
    _write_jsonl(args.out, candidates)
    _write_jsonl(args.gold_out, gold)
    print(f"wrote {len(candidates)} candidates -> {args.out}")
    print(f"wrote {len(gold)} gold candidates -> {args.gold_out}")


if __name__ == "__main__":
    main()
