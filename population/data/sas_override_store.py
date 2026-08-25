"""SAS override candidate lookup with pinned artifact provenance."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ARTIFACT = (
    Path(__file__).resolve().parents[2]
    / "datasets"
    / "pharmfreq"
    / "sas_override_gold_candidates.jsonl"
)


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
    rsids: tuple[str, ...]
    gnomad_status: str
    assembly: str
    override_type: str
    threshold: str

    @classmethod
    def from_row(cls, row: dict[str, object]) -> SasOverrideCandidate:
        return cls(
            gene=str(row["gene"]),
            chrom=str(row["chrom"]),
            pos=int(row["pos"]),
            ref=str(row["ref"]),
            alt=str(row["alt"]),
            af_indian_9768=float(row["af_indian_9768"]),
            af_nfe_gnomad=float(row["af_nfe_gnomad"]),
            af_ratio=None if row.get("af_ratio") is None else float(row["af_ratio"]),
            ac_nfe=int(row["ac_nfe"]),
            an_nfe=int(row["an_nfe"]),
            rsids=tuple(str(rsid) for rsid in row.get("rsids", [])),
            gnomad_status=str(row["gnomad_status"]),
            assembly=str(row["assembly"]),
            override_type=str(row["override_type"]),
            threshold=str(row["threshold"]),
        )

    def to_flag(self) -> dict[str, object]:
        return {
            "rule": "P2_SAS_ENRICHED_EUR_RARE",
            "gene": self.gene,
            "chrom": self.chrom,
            "pos": self.pos,
            "ref": self.ref,
            "alt": self.alt,
            "rsids": list(self.rsids),
            "population": "SAS",
            "af_indian_9768": self.af_indian_9768,
            "af_nfe_gnomad": self.af_nfe_gnomad,
            "af_ratio": self.af_ratio,
            "ac_nfe": self.ac_nfe,
            "an_nfe": self.an_nfe,
            "assembly": self.assembly,
            "override_type": self.override_type,
            "threshold": self.threshold,
            "source": "GenomeIndia_9768 + gnomAD_r3_NFE",
        }


@lru_cache(maxsize=1)
def load_gold_candidates(path: str | None = None) -> tuple[SasOverrideCandidate, ...]:
    artifact = Path(path) if path else ARTIFACT
    candidates: list[SasOverrideCandidate] = []
    with artifact.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            candidates.append(SasOverrideCandidate.from_row(json.loads(line)))
    return tuple(candidates)


@lru_cache(maxsize=1)
def gold_candidates_by_rsid(path: str | None = None) -> dict[str, SasOverrideCandidate]:
    by_rsid: dict[str, SasOverrideCandidate] = {}
    for candidate in load_gold_candidates(path):
        for rsid in candidate.rsids:
            by_rsid[rsid] = candidate
    return by_rsid
