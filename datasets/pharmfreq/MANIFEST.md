# PharmFreq Dataset Manifest

Generated: 2026-08-25

This directory contains pinned, offline artifacts used by Anukriti's
population-aware PGx evidence layer. Runtime code should read the compact
derived artifacts; raw/public source files are kept only for reproducibility.

## GenomeIndia Public Summary Stats

- Source URL:
  `https://ibdc.dbt.gov.in/genomeindia/downloadfile?path=9768GI_SummaryStats.tar.gz`
- Source file: `9768GI_SummaryStats.tar.gz`
- Download command:
  `curl -L --max-time 600 -o /tmp/9768GI_SummaryStats.tar.gz 'https://ibdc.dbt.gov.in/genomeindia/downloadfile?path=9768GI_SummaryStats.tar.gz'`
- Source shape: autosomes 1-22, aggregate Indian AF, GRCh38 coordinates.
- Columns: `CHROM`, `POS`, `ID`, `REF`, `ALT`, `AF`
- No rsIDs in the public source rows used here; Anukriti maps known PGx
  variants by `chrom,pos,ref,alt`.

## Pinned Artifacts

- `genomeindia_9768_summary_frequencies.jsonl`
  - 10 known PGx records mapped into `AlleleFrequencyRecord` shape.
  - Population bucket: `SAS`
  - Provenance: `GenomeIndia`, `9768GI_SummaryStats_2025_public_aggregate`
- `genomeindia_9768_highfreq_candidates.jsonl`
  - 7,107 PGx-region records with GenomeIndia Indian AF > 5%.
- `gnomad_pgx_nfe_sas_frequencies.jsonl`
  - 516,349 coordinate-level gnomAD r3 PGx-region NFE/SAS records.
  - Large artifact: 157 MB. This path is marked for Git LFS in
    `.gitattributes`; Git LFS must be installed before committing/pushing.
- `sas_override_candidates.jsonl`
  - 3,040 SAS override candidates.
  - Threshold: GenomeIndia Indian AF > 5% and gnomAD NFE AF < 1%.
- `sas_override_gold_candidates.jsonl`
  - 117 rsID-backed gold candidates.
  - Definition: candidate is present in gnomAD with rsID(s), has Indian AF
    between 5% and 30%, and satisfies the same NFE rarity threshold.

## Reproducibility Commands

Build the known-variant GenomeIndia overlay:

```bash
./venv/bin/python scripts/ingest_genomeindia_frequencies.py \
  ../17675458c_genomeindia_pgx_variants.jsonl
```

Regenerate SAS override candidates from the in-repo gnomAD extract:

```bash
./venv/bin/python scripts/discover_sas_override_candidates.py
```

Expected output counts:

- `sas_override_candidates.jsonl`: 3,040 rows
- `sas_override_gold_candidates.jsonl`: 117 rows

## Runtime Boundary

These artifacts provide population-frequency evidence. They do not replace
the deterministic CPIC/PharmVar star-allele and phenotype engine. The runtime
may attach evidence flags such as `sas_enriched_eur_rare`, but LLM synthesis
must not use these files to decide genotypes, phenotypes, or CPIC actionability.
