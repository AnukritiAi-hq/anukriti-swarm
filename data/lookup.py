"""Unified deterministic lookup API with provenance.

Single entry point for all biomedical data queries. Every response
carries provenance metadata and confidence scoring.

Future: Will route to MCP servers (PharmGKB, gnomAD, federated datasets)
while maintaining the same interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from biomedical.schemas import AlleleRecord, GeneRecord, GuidelineRecord, PrevalenceRecord, Provenance
from data.pharmacogenes import ALLELES, GENES
from data.prevalence import get_phenotype_prevalence, get_prevalence
from guidelines.cpic import get_guidelines_for_gene, lookup_recommendation


@dataclass(frozen=True)
class LookupResult:
    """Unified lookup result with provenance and confidence."""

    query: str
    found: bool
    data: Any
    confidence: float
    provenance: Provenance | None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BiomedicalLookup:
    """Unified deterministic lookup API.

    All queries return LookupResult with provenance. Deterministic:
    same query always returns same result for same data version.
    """

    def gene(self, symbol: str) -> LookupResult:
        """Lookup gene metadata."""
        rec = GENES.get(symbol)
        return LookupResult(
            query=f"gene:{symbol}", found=rec is not None,
            data=rec, confidence=1.0 if rec else 0.0,
            provenance=rec.provenance if rec else None,
        )

    def alleles(self, gene: str) -> LookupResult:
        """Lookup all alleles for a gene."""
        recs = ALLELES.get(gene, [])
        return LookupResult(
            query=f"alleles:{gene}", found=bool(recs),
            data=recs, confidence=1.0 if recs else 0.0,
            provenance=recs[0].provenance if recs else None,
        )

    def allele(self, gene: str, allele: str) -> LookupResult:
        """Lookup a specific allele."""
        for rec in ALLELES.get(gene, []):
            if rec.allele == allele:
                return LookupResult(
                    query=f"allele:{gene}:{allele}", found=True,
                    data=rec, confidence=1.0, provenance=rec.provenance,
                )
        return LookupResult(query=f"allele:{gene}:{allele}", found=False, data=None, confidence=0.0, provenance=None)

    def prevalence(self, gene: str, population: str) -> LookupResult:
        """Lookup phenotype prevalence for a gene in a population."""
        recs = get_prevalence(gene, population)
        return LookupResult(
            query=f"prevalence:{gene}:{population}", found=bool(recs),
            data=recs, confidence=0.95 if recs else 0.0,
            provenance=recs[0].provenance if recs else None,
        )

    def guideline(self, gene: str, phenotype: str, drug: str) -> LookupResult:
        """Lookup CPIC guideline recommendation."""
        rec = lookup_recommendation(gene, phenotype, drug)
        return LookupResult(
            query=f"guideline:{gene}:{phenotype}:{drug}", found=rec is not None,
            data=rec, confidence=1.0 if rec else 0.0,
            provenance=Provenance(source="CPIC", version="2023.1") if rec else None,
        )

    def guidelines_for_gene(self, gene: str) -> LookupResult:
        """Lookup all guidelines for a gene."""
        recs = get_guidelines_for_gene(gene)
        return LookupResult(
            query=f"guidelines:{gene}", found=bool(recs),
            data=recs, confidence=1.0 if recs else 0.0,
            provenance=Provenance(source="CPIC", version="2023.1") if recs else None,
        )
