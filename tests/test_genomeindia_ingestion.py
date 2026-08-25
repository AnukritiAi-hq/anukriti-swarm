"""GenomeIndia public summary-stat ingestion tests."""

from __future__ import annotations

import tarfile
from typing import TYPE_CHECKING

from datasets.pharmfreq.allele_frequencies import AlleleFrequencyRecord
from scripts.ingest_genomeindia_frequencies import records_from_summary_stats

from population.data.frequency_store import FrequencyStore

if TYPE_CHECKING:
    from pathlib import Path


def test_ingests_public_summary_stats_from_extracted_tsv(tmp_path: Path) -> None:
    source = tmp_path / "9768GI_SummaryStats"
    source.mkdir()
    (source / "chr1.tsv").write_text(
        "\n".join(
            [
                "1\t97450058\trs3918290\tC\tT\t0.00031",
                "1\t97515787\t.\tA\tC\t0.00000",
                "chr1\t97579893\t.\tG\tC\t0.01970",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    records = records_from_summary_stats(source)

    by_rsid = {rec.rsid: rec for rec in records}
    assert by_rsid["rs3918290"].gene == "DPYD"
    assert by_rsid["rs3918290"].allele == "*2A"
    assert by_rsid["rs3918290"].population == "SAS"
    assert by_rsid["rs3918290"].sample_n == 9768
    assert by_rsid["rs3918290"].source == "GenomeIndia"
    assert by_rsid["rs75017182"].allele == "c.1129-5923C>G"


def test_ingests_public_summary_stats_from_tarball(tmp_path: Path) -> None:
    extracted = tmp_path / "raw"
    extracted.mkdir()
    raw = extracted / "chr10.tsv"
    raw.write_text("10\t94781859\t.\tG\tA\t0.27891\n", encoding="utf-8")

    tar_path = tmp_path / "9768GI_SummaryStats.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(raw, arcname="9768GI_SummaryStats/chr10.tsv")

    records = records_from_summary_stats(tar_path)

    assert len(records) == 1
    assert records[0].gene == "CYP2C19"
    assert records[0].allele == "*2"
    assert records[0].frequency == 0.27891


def test_ingests_focused_genomeindia_jsonl_extract(tmp_path: Path) -> None:
    source = tmp_path / "genomeindia_pgx_variants.jsonl"
    source.write_text(
        (
            '{"gene":"DPYD","chrom":"chr1","pos":97450058,"id":null,'
            '"ref":"C","alt":"T","af_indian_9768":0.00250716,'
            '"assembly":"GRCh38","source":"GenomeIndia_9768",'
            '"population":"INDIAN_AGGREGATE"}\n'
        ),
        encoding="utf-8",
    )

    records = records_from_summary_stats(source)

    assert len(records) == 1
    assert records[0].rsid == "rs3918290"
    assert records[0].allele == "*2A"
    assert records[0].frequency == 0.00250716


def test_frequency_store_can_overlay_genomeindia_records() -> None:
    baseline = AlleleFrequencyRecord(
        "CYP2C19",
        "*2",
        "SAS",
        0.36,
        15308,
        "gnomAD",
        "v4.0",
        "no_function",
    )
    genomeindia = AlleleFrequencyRecord(
        "CYP2C19",
        "*2",
        "SAS",
        0.27891,
        9768,
        "GenomeIndia",
        "9768GI_SummaryStats_2025_public_aggregate",
        "no_function",
    )

    store = FrequencyStore(records=[baseline, genomeindia])
    result = store.lookup("CYP2C19", "*2", "SAS")

    assert result.frequency == 0.27891
    assert result.source == "GenomeIndia"


def test_frequency_store_loads_pinned_genomeindia_artifact() -> None:
    store = FrequencyStore(use_genomeindia=True)

    result = store.lookup("DPYD", "M166V", "SAS")

    assert result.frequency == 0.0709242
    assert result.sample_n == 9768
    assert result.source == "GenomeIndia"
