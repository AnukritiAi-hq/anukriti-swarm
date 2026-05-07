"""Allele frequency lookup with provenance tracking.

Provides deterministic, auditable frequency lookups from the PharmFreq
dataset. Every lookup returns provenance metadata (source, version,
sample size) for full traceability.

Future: Will be backed by MCP Dataset server for real gnomAD/PharmFreq access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from datasets.pharmfreq.allele_frequencies import ALL_FREQUENCIES, AlleleFrequencyRecord


@dataclass(frozen=True)
class FrequencyLookupResult:
    """Result of a frequency lookup with full provenance."""

    gene: str
    allele: str
    population: str
    frequency: float | None
    sample_n: int | None
    function: str | None
    source: str
    version: str
    found: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class FrequencyStore:
    """Deterministic allele frequency lookup store.

    Indexes PharmFreq data for O(1) lookups by (gene, allele, population).
    All lookups are deterministic and return provenance metadata.
    """

    def __init__(self, records: list[AlleleFrequencyRecord] | None = None) -> None:
        self._records = records or ALL_FREQUENCIES
        self._index: dict[tuple[str, str, str], AlleleFrequencyRecord] = {}
        self._build_index()

    def _build_index(self) -> None:
        for rec in self._records:
            key = (rec.gene, rec.allele, rec.population)
            self._index[key] = rec

    def lookup(self, gene: str, allele: str, population: str) -> FrequencyLookupResult:
        """Lookup allele frequency for a gene/allele/population combination.

        Always returns a result — if not found, result.found is False.
        """
        key = (gene, allele, population)
        rec = self._index.get(key)

        if rec:
            return FrequencyLookupResult(
                gene=gene, allele=allele, population=population,
                frequency=rec.frequency, sample_n=rec.sample_n,
                function=rec.function, source=rec.source, version=rec.version,
                found=True,
            )
        return FrequencyLookupResult(
            gene=gene, allele=allele, population=population,
            frequency=None, sample_n=None, function=None,
            source="not_found", version="N/A", found=False,
        )

    def get_population_profile(self, gene: str, population: str) -> list[FrequencyLookupResult]:
        """Get all allele frequencies for a gene in a population."""
        results = []
        for rec in self._records:
            if rec.gene == gene and rec.population == population:
                results.append(FrequencyLookupResult(
                    gene=rec.gene, allele=rec.allele, population=rec.population,
                    frequency=rec.frequency, sample_n=rec.sample_n,
                    function=rec.function, source=rec.source, version=rec.version,
                    found=True,
                ))
        return results

    def available_populations(self, gene: str) -> list[str]:
        """List populations with data for a gene."""
        return sorted({rec.population for rec in self._records if rec.gene == gene})

    def available_genes(self) -> list[str]:
        """List all genes in the store."""
        return sorted({rec.gene for rec in self._records})
