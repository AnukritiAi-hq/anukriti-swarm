"""``ConflictDetectionAgent`` — deterministic pharmacogenomic conflict check.

Phase 1 of the Evidence Sufficiency Layer brief.

Runs *after* the coverage analyzer. Where the analyzer asks "do we
have evidence for each facet?", this agent asks "does that evidence
**agree with itself**?" It detects exactly three pharmacogenomic
conflict classes — listed in the ``conflict/`` package docstring —
and nothing else. No general-purpose contradiction reasoner, no LLM
judgement, no heuristic "semantic similarity" scoring.

The three conflict classes (closed set)
---------------------------------------

    PHENOTYPE_DISAGREEMENT     two sources predict different
                               metabolizer phenotypes for the same
                               ``(gene, diplotype, population)``
                               tuple

    RECOMMENDATION_CLASH       two sources produce recommendations
                               that map to incompatible actions for
                               the same ``(drug, gene, phenotype)``
                               tuple; "incompatible" is a pairwise
                               check over a closed action enum
                               (USE / AVOID / CONSIDER_ALT /
                                CONTRAINDICATED) — any pair other
                               than USE+CONSIDER_ALT is a clash

    POPULATION_DIVERGENCE      two frequency-evidence references for
                               the same ``(allele, population)`` pair
                               report materially different frequencies
                               (|Δ| > tolerance, default 0.15 absolute)

Anything that doesn't fit one of these three is not this agent's
concern. That is the scope firewall.

Inputs
------

``detect(claims, *, tolerance=0.15) -> tuple[ConflictFinding, ...]``

``claims`` is an iterable of uniformly-shaped dicts the upstream
stack already produces. The recognized kinds (by the ``kind`` key):

    kind='phenotype'      {gene, diplotype, population, phenotype,
                           source_id}
    kind='recommendation' {drug, gene, phenotype, action_text,
                           source_id}
    kind='frequency'      {allele, population, frequency, source_id}

Everything else (``kind`` unknown or keys missing) is ignored — the
agent is deterministic about what it can read, not about what it
cannot.

Output
------

A tuple of ``ConflictFinding`` records. Empty tuple means no
conflict detected. The findings are sorted by ``(kind, reason)`` so
the audit trail is stable across runs.

Composition with ClaimCoverageAnalysis
--------------------------------------

``apply_to(analysis, findings)`` returns a new
``ClaimCoverageAnalysis`` with its ``CONFLICT_FREE`` facet
downgraded when findings exist:

    any HARD finding   CONFLICT_FREE -> MISSING
    only SOFT findings CONFLICT_FREE -> UNCERTAIN
    no findings        CONFLICT_FREE unchanged (COVERED)

The offending ``source_id`` list is merged into
``facet_evidence_refs[CONFLICT_FREE]`` so the audit names exactly
which sources disagree. Nothing else on the analysis changes — the
5 other facets are preserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from core.evidence_sufficiency.coverage.claim_coverage import (
    ClaimCoverageAnalysis,
    ClaimEvidenceFacet,
    FacetCoverageState,
)


# ---------------------------------------------------------------------------
# Closed enums
# ---------------------------------------------------------------------------


class ConflictKind(str, Enum):
    """The three recognized conflict classes — closed set."""

    PHENOTYPE_DISAGREEMENT = "phenotype_disagreement"
    RECOMMENDATION_CLASH = "recommendation_clash"
    POPULATION_DIVERGENCE = "population_divergence"


class ConflictSeverity(str, Enum):
    """Two severities — HARD forces MISSING on CONFLICT_FREE, SOFT forces UNCERTAIN.

    Phenotype disagreements are always HARD (the downstream rule
    engine cannot pick a side). Recommendation clashes are HARD
    (safety directives contradicting each other is a block). Population
    divergence is SOFT by default (frequencies often differ by cohort;
    flag for review but don't block).
    """

    HARD = "hard"
    SOFT = "soft"


class RecommendationAction(str, Enum):
    """Normalized recommendation action family — closed set.

    Any recommendation text the agent can't map to one of these is
    treated as ``UNKNOWN`` and excluded from clash detection — the
    agent refuses to guess.
    """

    USE = "use"
    AVOID = "avoid"
    CONSIDER_ALT = "consider_alt"
    CONTRAINDICATED = "contraindicated"
    UNKNOWN = "unknown"


# Pairs that *do not* clash. Every other pair (where both sides are
# non-UNKNOWN) is a clash.
_COMPATIBLE_ACTION_PAIRS: frozenset[frozenset[RecommendationAction]] = frozenset(
    {
        frozenset({RecommendationAction.USE, RecommendationAction.CONSIDER_ALT}),
        frozenset({RecommendationAction.AVOID, RecommendationAction.CONTRAINDICATED}),
        frozenset({RecommendationAction.AVOID, RecommendationAction.CONSIDER_ALT}),
        frozenset({RecommendationAction.CONTRAINDICATED, RecommendationAction.CONSIDER_ALT}),
    }
)


# Keyword tables used by ``_classify_action``. Lowercased; matched by
# substring. Closed set — adding a new action family is a code change.
_ACTION_KEYWORDS: dict[RecommendationAction, tuple[str, ...]] = {
    RecommendationAction.CONTRAINDICATED: (
        "contraindicated", "contraindication", "do not use",
        "do not prescribe", "must not", "never prescribe",
    ),
    RecommendationAction.AVOID: (
        "avoid", "do not give", "withhold",
    ),
    RecommendationAction.CONSIDER_ALT: (
        "consider alternative", "alternative", "prasugrel",
        "ticagrelor", "morphine",  # explicit alt-drug mentions
        "consider ", "use alternative",
    ),
    RecommendationAction.USE: (
        "use ", "prescribe ", "initiate ", "give ",
        "standard dose", "normal dose",
    ),
}


def _classify_action(text: str) -> RecommendationAction:
    """Map recommendation text to a closed action enum. Deterministic."""

    if not text:
        return RecommendationAction.UNKNOWN
    lowered = text.lower()
    # Check in priority order: contraindicated > avoid > consider_alt > use.
    # This mirrors the safety hierarchy — the most restrictive match wins.
    for action in (
        RecommendationAction.CONTRAINDICATED,
        RecommendationAction.AVOID,
        RecommendationAction.CONSIDER_ALT,
        RecommendationAction.USE,
    ):
        for kw in _ACTION_KEYWORDS[action]:
            if kw in lowered:
                return action
    return RecommendationAction.UNKNOWN


# ---------------------------------------------------------------------------
# Finding record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConflictFinding:
    """Frozen per-conflict audit record.

    Fields
    ------
    kind            which of the three closed conflict classes
    severity        HARD / SOFT (drives facet downgrade)
    reason          human-readable explanation
    source_ids      tuple of offending source ids (PMID / CPIC id /
                    PharmGKB id), sorted
    key             the tuple identity the conflict is keyed on — for
                    phenotype: (gene, diplotype, pop); for recommendation:
                    (drug, gene, phenotype); for frequency:
                    (allele, population). Strings only; stable across runs.
    magnitudes      optional payload carrying per-finding numerical
                    detail, e.g. ``("0.36", "0.12")`` for frequency
                    divergence. Tuple of strings so the whole record
                    is freely hashable/serializable.
    """

    kind: ConflictKind
    severity: ConflictSeverity
    reason: str
    source_ids: tuple[str, ...]
    key: tuple[str, ...]
    magnitudes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "severity": self.severity.value,
            "reason": self.reason,
            "source_ids": list(self.source_ids),
            "key": list(self.key),
            "magnitudes": list(self.magnitudes),
        }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


@dataclass
class ConflictDetectionAgent:
    """Deterministic pharmacogenomic conflict detector.

    Stateless. One instance handles many runs.

    Options
    -------
    ``frequency_tolerance`` : float, default 0.15
        Maximum absolute frequency delta allowed between two sources
        reporting the same (allele, population). Beyond this a
        POPULATION_DIVERGENCE finding is raised.
    """

    frequency_tolerance: float = 0.15

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        claims: Iterable[dict[str, Any]],
        *,
        tolerance: float | None = None,
    ) -> tuple[ConflictFinding, ...]:
        """Return all conflicts detected across ``claims``.

        Empty tuple == no conflict. Findings are returned sorted by
        ``(kind, reason)`` so repeat runs over the same inputs
        produce identical outputs.
        """

        tol = self.frequency_tolerance if tolerance is None else float(tolerance)
        bucketed = self._bucket_claims(claims)

        findings: list[ConflictFinding] = []
        findings.extend(self._detect_phenotype_conflicts(bucketed["phenotype"]))
        findings.extend(self._detect_recommendation_conflicts(bucketed["recommendation"]))
        findings.extend(self._detect_frequency_conflicts(bucketed["frequency"], tol))

        findings.sort(key=lambda f: (f.kind.value, f.reason))
        return tuple(findings)

    def apply_to(
        self,
        analysis: ClaimCoverageAnalysis,
        findings: Iterable[ConflictFinding],
    ) -> ClaimCoverageAnalysis:
        """Return a new analysis with CONFLICT_FREE downgraded when warranted.

        HARD finding present -> CONFLICT_FREE = MISSING (blocks synthesis)
        only SOFT findings   -> CONFLICT_FREE = UNCERTAIN
        no findings          -> analysis unchanged
        """

        findings_list = list(findings)
        if not findings_list:
            return analysis

        any_hard = any(f.severity is ConflictSeverity.HARD for f in findings_list)
        refs: list[str] = []
        for f in findings_list:
            refs.extend(f.source_ids)
        refs_tuple = tuple(dict.fromkeys(refs))  # dedup, preserve order

        reason_parts = [f"{f.kind.value}: {f.reason}" for f in findings_list]
        reason = "; ".join(reason_parts)

        new_state = (
            FacetCoverageState.MISSING if any_hard else FacetCoverageState.UNCERTAIN
        )
        return analysis.with_facet(
            ClaimEvidenceFacet.CONFLICT_FREE,
            state=new_state,
            evidence_refs=refs_tuple,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Bucketing
    # ------------------------------------------------------------------

    @staticmethod
    def _bucket_claims(
        claims: Iterable[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        buckets: dict[str, list[dict[str, Any]]] = {
            "phenotype": [],
            "recommendation": [],
            "frequency": [],
        }
        for c in claims or ():
            if not isinstance(c, dict):
                continue
            kind = str(c.get("kind", "")).strip().lower()
            if kind in buckets:
                buckets[kind].append(c)
        return buckets

    # ------------------------------------------------------------------
    # Per-kind detectors
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_phenotype_conflicts(
        items: list[dict[str, Any]],
    ) -> list[ConflictFinding]:
        # Group by (gene, diplotype, population); any bucket with >1
        # distinct phenotype is a conflict. Missing keys bail cleanly.
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for item in items:
            gene = str(item.get("gene", "")).strip().upper()
            diplo = str(item.get("diplotype", "")).strip()
            pop = str(item.get("population", "")).strip().upper()
            if not (gene and diplo and pop):
                continue
            groups.setdefault((gene, diplo, pop), []).append(item)

        findings: list[ConflictFinding] = []
        for key, group in groups.items():
            phenos = {
                str(i.get("phenotype", "")).strip().lower()
                for i in group
                if i.get("phenotype")
            }
            if len(phenos) > 1:
                source_ids = tuple(
                    sorted(
                        {str(i.get("source_id", "")) for i in group if i.get("source_id")}
                    )
                )
                findings.append(
                    ConflictFinding(
                        kind=ConflictKind.PHENOTYPE_DISAGREEMENT,
                        severity=ConflictSeverity.HARD,
                        reason=(
                            f"{key[0]} {key[1]} in {key[2]} predicted as "
                            + " / ".join(sorted(phenos))
                        ),
                        source_ids=source_ids,
                        key=tuple(key),
                    )
                )
        return findings

    @staticmethod
    def _detect_recommendation_conflicts(
        items: list[dict[str, Any]],
    ) -> list[ConflictFinding]:
        # Group by (drug, gene, phenotype); any bucket whose classified
        # actions contain a non-compatible pair is a clash.
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for item in items:
            drug = str(item.get("drug", "")).strip().lower()
            gene = str(item.get("gene", "")).strip().upper()
            phen = str(item.get("phenotype", "")).strip().lower()
            if not (drug and gene and phen):
                continue
            groups.setdefault((drug, gene, phen), []).append(item)

        findings: list[ConflictFinding] = []
        for key, group in groups.items():
            actions = [
                _classify_action(str(i.get("action_text", "")))
                for i in group
            ]
            actions_set = {a for a in actions if a is not RecommendationAction.UNKNOWN}
            if len(actions_set) < 2:
                continue
            # Check every pair; if any pair is *not* in the compatible set,
            # record a single finding covering all sources in this group.
            clash = False
            for a in actions_set:
                for b in actions_set:
                    if a is b:
                        continue
                    if frozenset({a, b}) not in _COMPATIBLE_ACTION_PAIRS:
                        clash = True
                        break
                if clash:
                    break
            if clash:
                source_ids = tuple(
                    sorted(
                        {str(i.get("source_id", "")) for i in group if i.get("source_id")}
                    )
                )
                findings.append(
                    ConflictFinding(
                        kind=ConflictKind.RECOMMENDATION_CLASH,
                        severity=ConflictSeverity.HARD,
                        reason=(
                            f"{key[0]} for {key[1]}/{key[2]}: "
                            + " vs ".join(sorted(a.value for a in actions_set))
                        ),
                        source_ids=source_ids,
                        key=tuple(key),
                    )
                )
        return findings

    @staticmethod
    def _detect_frequency_conflicts(
        items: list[dict[str, Any]],
        tolerance: float,
    ) -> list[ConflictFinding]:
        # Group by (allele, population); within each, find the min/max
        # frequency. If |max - min| > tolerance, emit a finding.
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for item in items:
            allele = str(item.get("allele", "")).strip()
            pop = str(item.get("population", "")).strip().upper()
            if not (allele and pop):
                continue
            try:
                float(item.get("frequency"))
            except (TypeError, ValueError):
                continue
            groups.setdefault((allele, pop), []).append(item)

        findings: list[ConflictFinding] = []
        for key, group in groups.items():
            freqs = [(float(i["frequency"]), i) for i in group]
            lo = min(freqs, key=lambda x: x[0])
            hi = max(freqs, key=lambda x: x[0])
            if hi[0] - lo[0] <= tolerance:
                continue
            source_ids = tuple(
                sorted(
                    {
                        str(lo[1].get("source_id", "")),
                        str(hi[1].get("source_id", "")),
                    }
                    - {""}
                )
            )
            findings.append(
                ConflictFinding(
                    kind=ConflictKind.POPULATION_DIVERGENCE,
                    severity=ConflictSeverity.SOFT,
                    reason=(
                        f"{key[0]} in {key[1]} reported as "
                        f"{lo[0]:.3f} vs {hi[0]:.3f} "
                        f"(Δ={hi[0] - lo[0]:.3f} > tol={tolerance:.2f})"
                    ),
                    source_ids=source_ids,
                    key=tuple(key),
                    magnitudes=(f"{lo[0]:.4f}", f"{hi[0]:.4f}"),
                )
            )
        return findings


__all__ = [
    "ConflictKind",
    "ConflictSeverity",
    "RecommendationAction",
    "ConflictFinding",
    "ConflictDetectionAgent",
]
