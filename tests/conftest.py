"""Shared pytest fixtures for the anukriti-swarm test suite.

This file is the single source of truth for test fixtures used by
multiple test modules. If a fixture is only used by one test file
it should live there, not here.

Fixture conventions
-------------------
* ``covered_analysis``   — canonical all-COVERED ClaimCoverageAnalysis
                           keyed on the flagship scope (clopidogrel +
                           CYP2C19 + *2/*2 + SAS)
* ``empty_analysis``     — all-MISSING starting point; tests append
                           facets via ``.with_facet`` to exercise rules
* ``boundary``           — GenerativeBoundary instance (default policy)
* ``resolver``           — ConflictResolver instance

Why these specific scopes? Flagship scenarios are the most-exercised
pharmacogenomic tuples in the codebase; using them as fixture defaults
means test failures surface in a biomedically meaningful form rather
than as abstract rule-table mismatches.

Test doubles
------------
``FakePopIndexer`` below replaces the real ``PopulationGraphIndexer``
for bias-detector tests. It exposes the two methods the detector
reads (``alleles_for``, ``evidence_for``) with caller-controllable
return values, so tests can drive every bias-rule code path without
building a full KG.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# sys.path setup — keep tests runnable directly via `pytest` from repo root
# without requiring the package to be pip-installed. The project already
# uses module-as-script idioms (``python -m demos.showcase``), so this
# matches the runtime convention.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Closed-enum / fixture imports (after sys.path setup)
# ---------------------------------------------------------------------------

from core.evidence_sufficiency.coverage.claim_coverage import (  # noqa: E402
    ALL_FACETS,
    ClaimCoverageAnalysis,
    ClaimEvidenceFacet,
    FacetCoverageState,
)
from core.models.population import SuperPopulation  # noqa: E402
from core.orchestrator.boundary import GenerativeBoundary  # noqa: E402
from core.orchestrator.conflict import ConflictResolver  # noqa: E402

# ---------------------------------------------------------------------------
# Canonical scope keys (flagship scenario)
# ---------------------------------------------------------------------------

FLAGSHIP_DRUG = "clopidogrel"
FLAGSHIP_GENE = "CYP2C19"
FLAGSHIP_GENOTYPE = "*2/*2"
FLAGSHIP_POPULATION = SuperPopulation.SAS


# ---------------------------------------------------------------------------
# Coverage-analysis fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def empty_analysis() -> ClaimCoverageAnalysis:
    """All-MISSING starting analysis on the flagship scope.

    Use this as the base for tests that need to construct a specific
    coverage state — chain ``.with_facet`` calls to cover each facet
    the test needs.
    """
    return ClaimCoverageAnalysis.empty(
        drug=FLAGSHIP_DRUG,
        gene=FLAGSHIP_GENE,
        genotype=FLAGSHIP_GENOTYPE,
        population=FLAGSHIP_POPULATION,
        correlation_id="test-correlation",
    )


@pytest.fixture
def covered_analysis(empty_analysis: ClaimCoverageAnalysis) -> ClaimCoverageAnalysis:
    """All-COVERED analysis on the flagship scope.

    Every facet COVERED with a plausible evidence ref. Tests that
    want to see "happy path" behaviour start here; tests that want
    to see a specific rule fire downgrade one or more facets via
    ``.with_facet``.
    """
    result = empty_analysis
    for facet in ALL_FACETS:
        result = result.with_facet(
            facet,
            state=FacetCoverageState.COVERED,
            evidence_refs=(f"src:{facet.value}-1",),
            reason=f"covered by src:{facet.value}-1",
        )
    return result


def make_analysis_with_state(
    *,
    base: ClaimCoverageAnalysis,
    overrides: dict[ClaimEvidenceFacet, FacetCoverageState],
) -> ClaimCoverageAnalysis:
    """Helper for tests that need a specific multi-facet state layout.

    Starts from ``base`` and applies each (facet, state) pair in
    ``overrides``. For COVERED/UNCERTAIN states a token evidence
    ref is attached so downstream code that inspects refs still
    has something to read. For MISSING the refs tuple is emptied.
    """
    result = base
    for facet, state in overrides.items():
        if state is FacetCoverageState.MISSING:
            refs: tuple[str, ...] = ()
            reason = f"no evidence for {facet.value}"
        else:
            refs = (f"src:{facet.value}-{state.value}",)
            reason = f"{state.value} evidence for {facet.value}"
        result = result.with_facet(facet, state=state, evidence_refs=refs, reason=reason)
    return result


# ---------------------------------------------------------------------------
# Orchestrator fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def boundary() -> GenerativeBoundary:
    """Default-policy GenerativeBoundary.

    Forbidden actions are the 4 documented in ``boundary.py``:
    INFER_PHENOTYPE / OVERRIDE_RECOMMENDATION / BYPASS_VERIFICATION
    / FABRICATE_CLAIM.
    """
    return GenerativeBoundary()


@pytest.fixture
def resolver() -> ConflictResolver:
    """Default ConflictResolver instance."""
    return ConflictResolver()


# ---------------------------------------------------------------------------
# Population-indexer test double (for bias-detector tests)
# ---------------------------------------------------------------------------


@dataclass
class FakePopIndexer:
    """Test double for ``PopulationGraphIndexer``.

    Exposes the two methods the bias detector reads:

    * ``alleles_for(pop)`` — returns the configured allele list
    * ``evidence_for(pop)`` — returns the configured evidence list

    Defaults produce empty lists so a test that only configures
    some populations keeps the rest "unknown". Use the factory
    helpers below to build common shapes.
    """

    alleles: dict[SuperPopulation, list[str]] = field(default_factory=dict)
    evidence: dict[SuperPopulation, list[str]] = field(default_factory=dict)

    def alleles_for(
        self, pop: SuperPopulation, *, gene: str | None = None,
    ) -> list[str]:
        # ``gene`` mirrors the real ``PopulationGraphIndexer.alleles_for``
        # kwarg (added when the bias detector started gene-scoping its
        # ANCESTRY_SCARCITY / UNSUPPORTED_EXTRAPOLATION rules). The fake
        # stores plain string allele names; it cannot read
        # ``payload["gene"]`` like the real indexer does.
        #
        # Filtering policy: only **exclude** entries that visibly belong
        # to a *different* gene (entries shaped like ``GENE*<allele>``
        # whose prefix doesn't match ``gene``). Plain opaque names like
        # ``"a1"`` pass through unchanged so existing tests that don't
        # care about gene scoping keep working without per-test
        # rewrites. When ``gene`` is None (default), behaviour is
        # identical to the original implementation.
        items = list(self.alleles.get(pop, []))
        if gene:
            gene_u = gene.upper()
            kept: list[str] = []
            for a in items:
                au = a.upper()
                if "*" in au:
                    prefix = au.split("*", 1)[0]
                    if prefix and prefix != gene_u:
                        continue  # belongs to a different gene
                kept.append(a)
            items = kept
        return items

    def evidence_for(self, pop: SuperPopulation) -> list[str]:
        return list(self.evidence.get(pop, []))


def make_pop_indexer(
    *,
    alleles: dict[SuperPopulation, list[str]] | None = None,
    evidence: dict[SuperPopulation, list[str]] | None = None,
) -> FakePopIndexer:
    """Build a FakePopIndexer with the supplied alleles/evidence maps."""
    return FakePopIndexer(
        alleles=dict(alleles or {}),
        evidence=dict(evidence or {}),
    )


__all__ = [
    "FLAGSHIP_DRUG",
    "FLAGSHIP_GENE",
    "FLAGSHIP_GENOTYPE",
    "FLAGSHIP_POPULATION",
    "FakePopIndexer",
    "empty_analysis",
    "covered_analysis",
    "boundary",
    "resolver",
    "make_analysis_with_state",
    "make_pop_indexer",
]
