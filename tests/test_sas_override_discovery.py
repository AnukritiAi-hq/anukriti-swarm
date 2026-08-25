"""GenomeIndia SAS override discovery tests."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from scripts.discover_sas_override_candidates import (
    discover_candidates,
    gold_candidates,
    read_gnomad_frequencies,
)

from population.data.sas_override_store import gold_candidates_by_rsid, load_gold_candidates


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_discovers_gnomad_present_and_absent_sas_override_candidates_from_tsv(
    tmp_path: Path,
) -> None:
    highfreq = tmp_path / "genomeindia_9768_highfreq_candidates.jsonl"
    _write_jsonl(
        highfreq,
        [
            {
                "gene": "DPYD",
                "chrom": "chr1",
                "pos": 97883329,
                "id": None,
                "ref": "A",
                "alt": "G",
                "af_indian_9768": 0.252994,
            },
            {
                "gene": "DPYD",
                "chrom": "chr1",
                "pos": 97450753,
                "id": None,
                "ref": "G",
                "alt": "C",
                "af_indian_9768": 0.83451,
            },
            {
                "gene": "DPYD",
                "chrom": "chr1",
                "pos": 97452581,
                "id": None,
                "ref": "T",
                "alt": "A",
                "af_indian_9768": 0.389315,
            },
            {
                "gene": "CYP2C9",
                "chrom": "chr10",
                "pos": 94981296,
                "id": None,
                "ref": "A",
                "alt": "C",
                "af_indian_9768": 0.100235,
            },
        ],
    )
    gnomad = tmp_path / "gnomad_eur.tsv"
    gnomad.write_text(
        "\n".join(
            [
                "chrom\tpos\tref\talt\taf_eur",
                "1\t97883329\tA\tG\t0.001",
                "1\t97450753\tG\tC\t0.000",
                "10\t94981296\tA\tC\t0.025",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    candidates = discover_candidates(highfreq, gnomad)

    assert [candidate.pos for candidate in candidates] == [97452581, 97450753, 97883329]

    absent = candidates[0]
    assert absent.gnomad_status == "not_in_gnomad"
    assert absent.af_nfe_gnomad == 0
    assert absent.af_ratio is None

    known = candidates[2]
    assert known.gnomad_status == "in_gnomad"
    assert known.rsids == ["rs1801265"]
    assert known.af_ratio == 252.99
    assert gold_candidates(candidates) == [known]


def test_reads_gnomad_jsonl_frequency_extract(tmp_path: Path) -> None:
    source = tmp_path / "gnomad_suffixless"
    _write_jsonl(
        source,
        [
            {
                "chrom": "chr1",
                "pos": 97450753,
                "ref": "G",
                "alt": "C",
                "AF_non_finnish_european": 0.003,
            }
        ],
    )
    with source.open("ab") as handle:
        handle.write(b"\x00\x00\x00\n")

    result = read_gnomad_frequencies(source)

    assert result[("1", 97450753, "G", "C")].af_nfe == 0.003


def test_reads_gnomad_vcf_frequency_extract_with_multiallelic_af(tmp_path: Path) -> None:
    source = tmp_path / "gnomad.vcf"
    source.write_text(
        "\n".join(
            [
                "##fileformat=VCFv4.2",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
                "1\t97450753\t.\tG\tA,C\t.\tPASS\tAF_nfe=0.2,0.004",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = read_gnomad_frequencies(source)

    assert result[("1", 97450753, "G", "A")].af_nfe == 0.2
    assert result[("1", 97450753, "G", "C")].af_nfe == 0.004


def test_candidate_records_are_json_serializable(tmp_path: Path) -> None:
    highfreq = tmp_path / "genomeindia.jsonl"
    _write_jsonl(
        highfreq,
        [
            {
                "gene": "DPYD",
                "chrom": "chr1",
                "pos": 97450753,
                "ref": "G",
                "alt": "C",
                "af_indian_9768": 0.83451,
            }
        ],
    )
    gnomad = tmp_path / "gnomad.tsv"
    gnomad.write_text("chrom,pos,ref,alt,AF_EUR\n1,97450753,G,C,0\n", encoding="utf-8")

    candidates = discover_candidates(highfreq, gnomad)

    assert json.loads(json.dumps(asdict(candidates[0])))["af_nfe_gnomad"] == 0.0


def test_pinned_sas_override_artifacts_are_loadable() -> None:
    root = Path(__file__).resolve().parent.parent / "datasets" / "pharmfreq"
    candidates_path = root / "sas_override_candidates.jsonl"
    gold_path = root / "sas_override_gold_candidates.jsonl"

    candidates = [json.loads(line) for line in candidates_path.read_text().splitlines()]
    gold = [json.loads(line) for line in gold_path.read_text().splitlines()]

    assert len(candidates) == 3040
    assert len(gold) == 117
    assert all(row["af_indian_9768"] > 0.05 for row in candidates)
    assert all(row["af_nfe_gnomad"] < 0.01 for row in candidates)
    assert all(row["rsids"] for row in gold)
    assert {row["gnomad_status"] for row in gold} == {"in_gnomad"}
    assert len(
        [
            row
            for row in candidates
            if row["rsids"]
            and row["gnomad_status"] == "in_gnomad"
            and 0.05 < row["af_indian_9768"] <= 0.30
        ]
    ) == len(gold)


def test_gold_candidate_store_indexes_dpyd_lead_rsids() -> None:
    candidates = load_gold_candidates()
    by_rsid = gold_candidates_by_rsid()

    assert len(candidates) == 117
    lead = by_rsid["rs549104824"]
    assert lead.gene == "DPYD"
    assert lead.af_indian_9768 == 0.108291
    assert lead.af_nfe_gnomad == 0.00013283
    assert lead.af_ratio == 815.26
    assert lead.to_flag()["override_type"] == "sas_enriched_eur_rare"
