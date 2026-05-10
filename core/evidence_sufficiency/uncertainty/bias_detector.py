"""``PopulationEvidenceBiasDetector`` — 3 closed ancestry-bias signals.

Phase 5, commit 15 of the Evidence Sufficiency Layer brief. Closes
requirement #20.

Detects three pharmacogenomic evidence-bias kinds — and nothing
else — over a ClaimCoverageAnalysis and (optionally) a populated
``PopulationGraphIndexer``. Deterministic: every input produces
the same output. No LLM. Each finding is a concrete measurement
backed by specific numeric thresholds the caller can override.

Why this matters
----------------

Pharmacogenomic evidence historically skews Eurocentric: most
curated allele-frequency datasets, CPIC guideline cohorts, and
PubMed abstracts over-sample European ancestry. A verification
layer that is population-aware must *name* this skew as a signal
rather than silently proceed on Eurocentric evidence when the
patient is non-EUR — otherwise "population-aware" is just a
label. This detector is the mechanism.

Closed bias kinds
-----------------

    EUROCENTRIC_IMBALANCE
        Target is a non-EUR super-population; evidence supporting
        the target population is empty or below a minimum, while
        EUR evidence is present. This is the canonical bias: the
        retrieval set is weighted toward EUR even though the
        query is about SAS / EAS / AFR / AMR.

    ANCESTRY_SCARCITY
        The target population's observed-allele count falls below
        a configurable fraction of the maximum-observed population
        in the graph. Distinct from EUROCENTRIC_IMBALANCE because
        the reference can be any population, not just EUR — e.g.
        SAS vs EAS when both are underrepresented relative to AFR
        on a given allele.

    UNSUPPORTED_EXTRAPOLATION
        POPULATION facet is UNCERTAIN and the retrieved alleles
        have NO frequency edges to the target population in the
        KG. Calling this out is a safety signal: the pipeline
        wants to reason about the target population using
        evidence that literally doesn't cover it.

All other bias classes — "sex-biased evidence", "age-biased
evidence", "publication bias", etc. — are **out of scope** for
this detector. Extending the set is a code change.

Output
------

``detect(coverage, pop_indexer=None, kg=None) -> tuple[BiasFinding, ...]``

Empty tuple means no bias detected. Findings are sorted by
``(kind, reason)`` for stable output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.evidence_sufficiency.coverage.claim_coverage import (
    ClaimCoverageAnalysis,
    ClaimEvidenceFacet,
    FacetCoverageState,
)
from core.models.population import SuperPopulation

# ---------------------------------------------------------------------------
# Closed enum
# ---------------------------------------------------------------------------


class BiasKind(str, Enum):
    """The three bias classes the detector recognises. Closed set."""

    EUROCENTRIC_IMBALANCE = "eurocentric_imbalance"
    ANCESTRY_SCARCITY = "ancestry_scarcity"
    UNSUPPORTED_EXTRAPOLATION = "unsupported_extrapolation"


# ---------------------------------------------------------------------------
# Frozen finding
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BiasFinding:
    """Frozen per-finding audit record.

    Fields
    ------
    kind         closed BiasKind
    target       the query's target SuperPopulation (what the
                 pipeline is reasoning about)
    reason       human-readable note naming the measurement
    measurements primitive-value dict (counts, ratios, source ids)
                 the caller can inspect for a richer reading;
                 JSON-safe
    """

    kind: BiasKind
    target: SuperPopulation
    reason: str
    measurements: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "target": self.target.value,
            "reason": self.reason,
            "measurements": dict(self.measurements),
        }


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------


@dataclass
class PopulationEvidenceBiasDetector:
    """Deterministic ancestry-bias detector.

    Stateless. One instance handles many runs.

    Options
    -------
    scarcity_ratio      default 0.5 — target is flagged
                        ANCESTRY_SCARCITY when its observed-allele
                        count is below this fraction of the
                        maximum-observed population's count.
    min_target_evidence default 1 — required minimum for the
                        target to escape EUROCENTRIC_IMBALANCE.
                        Below this (while EUR has any evidence)
                        fires the flag.
    """

    scarcity_ratio: float = 0.5
    min_target_evidence: int = 1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        coverage: ClaimCoverageAnalysis,
        *,
        pop_indexer: Any = None,
        kg: Any = None,
    ) -> tuple[BiasFinding, ...]:
        """Return all bias findings for ``coverage`` + optional KG context.

        ``pop_indexer`` — optional ``PopulationGraphIndexer``. When
        supplied, rules 1-3 have real frequency data to measure; without
        it the detector still emits a weaker UNSUPPORTED_EXTRAPOLATION
        finding if POPULATION is UNCERTAIN.

        ``kg`` — optional ``PharmacogenomicKnowledgeGraph``. Reserved for
        rules that need node lookup (not required for the current 3
        bias classes but accepted so future rules can use it without an
        API break).
        """

        target = coverage.population
        findings: list[BiasFinding] = []

        # Rule 1 — EUROCENTRIC_IMBALANCE
        if target is not SuperPopulation.EUR and pop_indexer is not None:
            eur_ev = len(pop_indexer.evidence_for(SuperPopulation.EUR))
            target_ev = len(pop_indexer.evidence_for(target))
            if target_ev < self.min_target_evidence and eur_ev > 0:
                findings.append(
                    BiasFinding(
                        kind=BiasKind.EUROCENTRIC_IMBALANCE,
                        target=target,
                        reason=(
                            f"{target.value} evidence count {target_ev} below "
                            f"minimum {self.min_target_evidence} while EUR "
                            f"evidence count is {eur_ev}"
                        ),
                        measurements={
                            "target_evidence_count": target_ev,
                            "eur_evidence_count": eur_ev,
                            "min_target_evidence": self.min_target_evidence,
                        },
                    )
                )

        # Rule 2 — ANCESTRY_SCARCITY
        if pop_indexer is not None:
            counts = {pop: len(pop_indexer.alleles_for(pop)) for pop in SuperPopulation}
            max_count = max(counts.values(), default=0)
            target_count = counts.get(target, 0)
            if max_count > 0:
                ratio = target_count / max_count
                if ratio < self.scarcity_ratio:
                    findings.append(
                        BiasFinding(
                            kind=BiasKind.ANCESTRY_SCARCITY,
                            target=target,
                            reason=(
                                f"{target.value} observed in {target_count} "
                                f"allele(s); max population has {max_count} "
                                f"(ratio {ratio:.2f} < {self.scarcity_ratio:.2f})"
                            ),
                            measurements={
                                "target_allele_count": target_count,
                                "max_allele_count": max_count,
                                "ratio": round(ratio, 4),
                                "scarcity_ratio": self.scarcity_ratio,
                                "all_counts": {pop.value: counts[pop] for pop in SuperPopulation},
                            },
                        )
                    )

        # Rule 3 — UNSUPPORTED_EXTRAPOLATION
        pop_state = coverage.facet_states[ClaimEvidenceFacet.POPULATION]
        if pop_state is FacetCoverageState.UNCERTAIN:
            target_has_freq_data = False
            if pop_indexer is not None:
                target_has_freq_data = len(pop_indexer.alleles_for(target)) > 0
            if not target_has_freq_data:
                findings.append(
                    BiasFinding(
                        kind=BiasKind.UNSUPPORTED_EXTRAPOLATION,
                        target=target,
                        reason=(
                            f"POPULATION facet is UNCERTAIN and no "
                            f"frequency data observed for {target.value}; "
                            f"extrapolating from non-{target.value} evidence "
                            f"is unsupported"
                        ),
                        measurements={
                            "pop_indexer_supplied": pop_indexer is not None,
                            "target_allele_count_in_kg": (
                                len(pop_indexer.alleles_for(target))
                                if pop_indexer is not None
                                else 0
                            ),
                        },
                    )
                )

        findings.sort(key=lambda f: (f.kind.value, f.reason))
        return tuple(findings)


__all__ = ["BiasKind", "BiasFinding", "PopulationEvidenceBiasDetector"]
