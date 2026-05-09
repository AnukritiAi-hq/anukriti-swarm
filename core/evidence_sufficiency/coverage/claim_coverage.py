"""``ClaimCoverageAnalysis`` — 6-facet evidence coverage record.

Phase 1 of the Evidence Sufficiency Layer (brief requirement #16).

This module defines the *shape* of a coverage reading: which of the
six closed evidence facets the platform requires for safe
pharmacogenomic synthesis are satisfied for a given run, and with
what evidence. It is a **frozen** dataclass — once the analyzer has
populated it, it is an audit record and must not be mutated.

The six facets
--------------
For every ``(drug, gene, population, genotype)`` tuple the platform
requires at least one piece of evidence for each of the following,
before any generative narrative may run:

    ALLELE          the star-allele / variant itself is attested in
                    a curated source (PharmGKB / PharmVar / PubMed)
    PHENOTYPE       the diplotype → phenotype mapping is backed by a
                    CPIC activity-score rule or equivalent
    CPIC            a CPIC guideline exists for this drug-gene pair
    POPULATION      allele frequency in the target super-population
                    is supported by a curated source
    RECOMMENDATION  an actionable prescribing recommendation is
                    attached to the phenotype in a guideline
    CONFLICT_FREE   the retrieved evidence set carries no unresolved
                    contradiction about any of the above five

The facet set is **closed**. Callers cannot add a seventh facet at
runtime; extending the set is a code change. That is the scope
firewall — it prevents the layer from drifting into generic
"did we find relevant docs?" territory.

Per-facet state
---------------
Each facet carries exactly one of three outcomes:

    COVERED         at least one non-conflicting evidence reference
                    resolves to a curated source for this facet
    MISSING         no evidence reference resolves for this facet
    UNCERTAIN       references exist but resolution or relevance is
                    inconclusive (e.g. source cited but MCP cache
                    couldn't confirm it's a curated pharmacogenomic
                    entry; or conflicting references observed for
                    CONFLICT_FREE)

No fourth state ("partial", "weak", "probable"). That deliberately
forbids LLM-ish gradations the brief rejects.

Scoring
-------
``coverage_ratio`` is ``n_covered / 6`` — a pure, deterministic
fraction in ``[0.0, 1.0]``. Two identical inputs always produce the
same score. Callers that want a richer reading should inspect the
per-facet ``facet_states`` map directly.

Composition
-----------
Downstream consumers:

    EvidenceCoverageAnalyzer (commit 3) produces this record
    ConflictDetectionAgent   (commit 4) sets CONFLICT_FREE facet
    SufficiencyDecisionEngine (commit 5) maps it to an action
    SetLevelEvidenceVerifier (phase 4) treats it as one input

Relationship to existing types
------------------------------
Not a replacement for ``GroundingReport.coverage`` (source-level:
"did the cited ids resolve?"). This is *facet-level* coverage:
"do we have evidence for each of the six required kinds?". Both
readings flow into ``SufficiencyDecisionEngine`` — they measure
different things.

The ``claim_id`` / ``correlation_id`` conventions match
``VerificationTrace`` so a ``ClaimCoverageAnalysis`` can be
persisted into MCP provenance alongside the run's other traces
without reshaping.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from core.models.population import SuperPopulation


# ---------------------------------------------------------------------------
# Closed enums — scope firewall at the type boundary
# ---------------------------------------------------------------------------


class ClaimEvidenceFacet(str, Enum):
    """The six pharmacogenomic evidence facets — closed set.

    Ordered as they appear in the safety synthesis contract: you
    cannot recommend a drug before you have established allele →
    phenotype → guideline → population → recommendation, and ruled
    out conflict.
    """

    ALLELE = "allele"
    PHENOTYPE = "phenotype"
    CPIC = "cpic"
    POPULATION = "population"
    RECOMMENDATION = "recommendation"
    CONFLICT_FREE = "conflict_free"


class FacetCoverageState(str, Enum):
    """Per-facet outcome — closed set (no gradations)."""

    COVERED = "covered"
    MISSING = "missing"
    UNCERTAIN = "uncertain"


# Canonical iteration order for the six facets. Used by the analyzer
# and verifier so report output is stable across runs.
ALL_FACETS: tuple[ClaimEvidenceFacet, ...] = (
    ClaimEvidenceFacet.ALLELE,
    ClaimEvidenceFacet.PHENOTYPE,
    ClaimEvidenceFacet.CPIC,
    ClaimEvidenceFacet.POPULATION,
    ClaimEvidenceFacet.RECOMMENDATION,
    ClaimEvidenceFacet.CONFLICT_FREE,
)


# ---------------------------------------------------------------------------
# Frozen audit record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClaimCoverageAnalysis:
    """Frozen per-run 6-facet coverage reading.

    Identity
    --------
    ``claim_id``        stable 16-char hex id; matches MCP
                        ``ProvenanceRecord.claim_id`` when persisted
    ``correlation_id``  orchestration run id this analysis belongs to

    Scope keys
    ----------
    The pharmacogenomic tuple the analysis is keyed on. Exactly the
    four fields the platform's core workflow consumes; extending
    them is a code change.

    ``drug``, ``gene``, ``genotype`` are strings (free-form names like
    "clopidogrel" / "CYP2C19" / "*2/*2" remain the repo's convention).
    ``population`` is ``SuperPopulation`` — closed enum at the
    boundary, so passing "SouthAsian" as a string fails at
    construction.

    Facet data
    ----------
    ``facet_states``        immutable mapping facet → state
    ``facet_evidence_refs`` immutable mapping facet → tuple of
                            evidence source ids (PMID / CPIC guideline
                            id / PharmGKB annotation id) that
                            contributed to that facet's state
    ``facet_reasons``       immutable mapping facet → human-readable
                            note; present for every facet, empty
                            string if there's nothing to add

    Both mappings are keyed by the *full* ALL_FACETS set. Absence
    of a facet key is an error: construction populates every facet,
    MISSING-with-empty-refs if nothing was found.

    Derived signals
    ---------------
    ``coverage_ratio``    n_covered / 6, deterministic
    ``is_complete``       True iff every facet is COVERED
    ``missing_facets``    facets whose state is MISSING (stable order)
    ``uncertain_facets``  facets whose state is UNCERTAIN (stable order)

    Mutation
    --------
    Frozen. ``with_facet(facet, state, refs, reason)`` returns a new
    ``ClaimCoverageAnalysis`` with one facet replaced. Used by the
    ``ConflictDetectionAgent`` in commit 4 to set the CONFLICT_FREE
    facet on a pre-existing analysis without touching the rest.
    """

    drug: str
    gene: str
    genotype: str
    population: SuperPopulation

    facet_states: Mapping[ClaimEvidenceFacet, FacetCoverageState]
    facet_evidence_refs: Mapping[ClaimEvidenceFacet, tuple[str, ...]]
    facet_reasons: Mapping[ClaimEvidenceFacet, str]

    claim_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    correlation_id: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def empty(
        cls,
        *,
        drug: str,
        gene: str,
        genotype: str,
        population: SuperPopulation,
        correlation_id: str = "",
    ) -> "ClaimCoverageAnalysis":
        """Build an all-MISSING analysis. Used as the starting point
        for the ``EvidenceCoverageAnalyzer``'s accumulation pass
        (commit 3)."""

        states: dict[ClaimEvidenceFacet, FacetCoverageState] = {
            facet: FacetCoverageState.MISSING for facet in ALL_FACETS
        }
        refs: dict[ClaimEvidenceFacet, tuple[str, ...]] = {
            facet: () for facet in ALL_FACETS
        }
        reasons: dict[ClaimEvidenceFacet, str] = {
            facet: "" for facet in ALL_FACETS
        }
        return cls(
            drug=drug,
            gene=gene,
            genotype=genotype,
            population=population,
            facet_states=MappingProxyType(states),
            facet_evidence_refs=MappingProxyType(refs),
            facet_reasons=MappingProxyType(reasons),
            correlation_id=correlation_id,
        )

    def with_facet(
        self,
        facet: ClaimEvidenceFacet,
        *,
        state: FacetCoverageState,
        evidence_refs: tuple[str, ...] = (),
        reason: str = "",
    ) -> "ClaimCoverageAnalysis":
        """Return a new analysis with one facet replaced.

        Preserves ``claim_id`` + ``correlation_id`` + ``created_at``
        so the audit trail is uninterrupted. Rejects unknown facets
        via the closed enum — there is no way to smuggle a seventh
        facet in.
        """

        if not isinstance(facet, ClaimEvidenceFacet):  # defensive; enum enforces
            raise TypeError(
                f"facet must be ClaimEvidenceFacet, got {type(facet).__name__}"
            )

        new_states = dict(self.facet_states)
        new_refs = dict(self.facet_evidence_refs)
        new_reasons = dict(self.facet_reasons)
        new_states[facet] = state
        new_refs[facet] = tuple(evidence_refs)
        new_reasons[facet] = reason

        return ClaimCoverageAnalysis(
            drug=self.drug,
            gene=self.gene,
            genotype=self.genotype,
            population=self.population,
            facet_states=MappingProxyType(new_states),
            facet_evidence_refs=MappingProxyType(new_refs),
            facet_reasons=MappingProxyType(new_reasons),
            claim_id=self.claim_id,
            correlation_id=self.correlation_id,
            created_at=self.created_at,
        )

    # ------------------------------------------------------------------
    # Derived signals (pure, deterministic)
    # ------------------------------------------------------------------

    @property
    def coverage_ratio(self) -> float:
        """Fraction of facets in ``COVERED`` state, in ``[0.0, 1.0]``.

        Six facets, so the denominator is always 6. No weighting —
        every facet counts equally. The sufficiency decision engine
        applies policy on top of this raw ratio (e.g.
        "missing RECOMMENDATION always blocks"); this property stays
        a dumb count so the audit is reproducible.
        """

        covered = sum(
            1
            for state in self.facet_states.values()
            if state is FacetCoverageState.COVERED
        )
        return round(covered / len(ALL_FACETS), 4)

    @property
    def is_complete(self) -> bool:
        """True iff every one of the six facets is COVERED."""

        return all(
            self.facet_states[facet] is FacetCoverageState.COVERED
            for facet in ALL_FACETS
        )

    @property
    def missing_facets(self) -> tuple[ClaimEvidenceFacet, ...]:
        """Facets whose state is MISSING, in ``ALL_FACETS`` order."""

        return tuple(
            facet
            for facet in ALL_FACETS
            if self.facet_states[facet] is FacetCoverageState.MISSING
        )

    @property
    def uncertain_facets(self) -> tuple[ClaimEvidenceFacet, ...]:
        """Facets whose state is UNCERTAIN, in ``ALL_FACETS`` order."""

        return tuple(
            facet
            for facet in ALL_FACETS
            if self.facet_states[facet] is FacetCoverageState.UNCERTAIN
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dict. Same shape/idiom as ``VerificationTrace.to_dict``
        so the analysis can be persisted alongside verification traces in
        the MCP provenance store without reshaping at the boundary."""

        return {
            "claim_id": self.claim_id,
            "correlation_id": self.correlation_id,
            "drug": self.drug,
            "gene": self.gene,
            "genotype": self.genotype,
            "population": self.population.value,
            "coverage_ratio": self.coverage_ratio,
            "is_complete": self.is_complete,
            "facets": [
                {
                    "facet": facet.value,
                    "state": self.facet_states[facet].value,
                    "evidence_refs": list(self.facet_evidence_refs[facet]),
                    "reason": self.facet_reasons[facet],
                }
                for facet in ALL_FACETS
            ],
            "missing_facets": [f.value for f in self.missing_facets],
            "uncertain_facets": [f.value for f in self.uncertain_facets],
            "created_at": self.created_at.isoformat(),
        }


__all__ = [
    "ClaimEvidenceFacet",
    "FacetCoverageState",
    "ALL_FACETS",
    "ClaimCoverageAnalysis",
]
