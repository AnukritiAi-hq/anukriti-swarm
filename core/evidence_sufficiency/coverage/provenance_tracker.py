"""``ProvenanceCoverageTracker`` — deterministic provenance-chain audit.

Phase 1 of the Evidence Sufficiency Layer brief.

Where ``EvidenceCoverageAnalyzer`` asks "do we have evidence for each
of the six pharmacogenomic facets?", this tracker asks a different
question: "is every claim's **provenance chain** complete and
attributable?" It reads ``MCPProvenanceStore``-shaped records and
returns a fixed 4-dimension attribution report.

The four attribution dimensions (closed set):

    RULE_ID                  every record carries a non-empty
                             ``rule_id``; generative-only records are
                             exempt under lenient mode (configurable)
    AGENT_ATTRIBUTION        every record carries a non-empty
                             ``generating_agent``; a chain of
                             anonymous records is not auditable
    CHAIN_COMPLETENESS       every record's ``parent_claim_id`` — if
                             non-empty — resolves to a record also
                             present in the correlation's record set
    EVIDENCE_RESOLVABILITY   at least one ``evidence_sources`` entry
                             per record that's marked
                             ``origin='deterministic'``; generative
                             records are checked only when strict

This tracker is deliberately narrow: it does not re-open documents
or reach out to MCP. It consumes a list of records the caller
already has (typically from ``MCPProvenanceStore.for_run`` or the
in-memory ``MCPPersistenceHook``'s buffer). That keeps the tracker
deterministic and unit-testable without a live MCP client.

Outputs
-------
``ProvenanceCoverageReport`` — a frozen dataclass enumerating which
attribution dimensions are COVERED vs MISSING for the run, plus
per-record diagnostic entries for any offending record_ids. The
report has a ``coverage_ratio`` property symmetric with
``ClaimCoverageAnalysis.coverage_ratio`` so both feed the
``SufficiencyDecisionEngine`` with the same arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

# ---------------------------------------------------------------------------
# Closed-enum dimensions
# ---------------------------------------------------------------------------


class ProvenanceDimension(str, Enum):
    """The four closed attribution dimensions. Extending is a code change."""

    RULE_ID = "rule_id"
    AGENT_ATTRIBUTION = "agent_attribution"
    CHAIN_COMPLETENESS = "chain_completeness"
    EVIDENCE_RESOLVABILITY = "evidence_resolvability"


class DimensionState(str, Enum):
    """Per-dimension outcome — closed set, no gradations."""

    COVERED = "covered"
    MISSING = "missing"


ALL_DIMENSIONS: tuple[ProvenanceDimension, ...] = (
    ProvenanceDimension.RULE_ID,
    ProvenanceDimension.AGENT_ATTRIBUTION,
    ProvenanceDimension.CHAIN_COMPLETENESS,
    ProvenanceDimension.EVIDENCE_RESOLVABILITY,
)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProvenanceCoverageReport:
    """Frozen per-run provenance-chain audit record.

    Fields
    ------
    correlation_id    orchestration run the report covers
    total_records     how many records were inspected
    dimension_states  immutable mapping dimension → state
    offenders         immutable mapping dimension → tuple of
                      offending ``claim_id`` strings
    reasons           immutable mapping dimension → human-readable
                      note (always populated, may be empty)

    Derived signals
    ---------------
    coverage_ratio    n_covered / 4, rounded to 4 decimals
    is_complete       True iff every dimension is COVERED
    missing_dimensions tuple of dimensions in MISSING state
                       (stable ALL_DIMENSIONS order)
    """

    correlation_id: str
    total_records: int
    dimension_states: Mapping[ProvenanceDimension, DimensionState]
    offenders: Mapping[ProvenanceDimension, tuple[str, ...]]
    reasons: Mapping[ProvenanceDimension, str]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def coverage_ratio(self) -> float:
        covered = sum(
            1 for state in self.dimension_states.values() if state is DimensionState.COVERED
        )
        return round(covered / len(ALL_DIMENSIONS), 4)

    @property
    def is_complete(self) -> bool:
        return all(self.dimension_states[d] is DimensionState.COVERED for d in ALL_DIMENSIONS)

    @property
    def missing_dimensions(self) -> tuple[ProvenanceDimension, ...]:
        return tuple(
            d for d in ALL_DIMENSIONS if self.dimension_states[d] is DimensionState.MISSING
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "total_records": self.total_records,
            "coverage_ratio": self.coverage_ratio,
            "is_complete": self.is_complete,
            "dimensions": [
                {
                    "dimension": d.value,
                    "state": self.dimension_states[d].value,
                    "offenders": list(self.offenders[d]),
                    "reason": self.reasons[d],
                }
                for d in ALL_DIMENSIONS
            ],
            "missing_dimensions": [d.value for d in self.missing_dimensions],
            "created_at": self.created_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Record-shape adapter
# ---------------------------------------------------------------------------


_REQUIRED_RECORD_KEYS = (
    "claim_id",
    "generating_agent",
    "rule_id",
    "correlation_id",
    "evidence_sources",
    "parent_claim_id",
    "origin",
)


def _as_record_dict(rec: Any) -> dict[str, Any] | None:
    """Normalize a record-like value to a dict with the required keys."""

    if rec is None:
        return None
    if isinstance(rec, dict):
        if all(k in rec for k in _REQUIRED_RECORD_KEYS):
            return rec
        # Some callers may pass records that include 'claim_id' as the only
        # strict requirement; fall back to defaults for missing fields.
        if "claim_id" in rec:
            return {
                "claim_id": rec.get("claim_id"),
                "generating_agent": rec.get("generating_agent", ""),
                "rule_id": rec.get("rule_id", ""),
                "correlation_id": rec.get("correlation_id", ""),
                "evidence_sources": list(rec.get("evidence_sources") or []),
                "parent_claim_id": rec.get("parent_claim_id", ""),
                "origin": rec.get("origin", "deterministic"),
            }
        return None
    # ProvenanceRecord dataclass
    if all(hasattr(rec, k) for k in _REQUIRED_RECORD_KEYS):
        return {
            "claim_id": rec.claim_id,
            "generating_agent": rec.generating_agent,
            "rule_id": rec.rule_id,
            "correlation_id": rec.correlation_id,
            "evidence_sources": list(rec.evidence_sources or []),
            "parent_claim_id": rec.parent_claim_id,
            "origin": getattr(rec, "origin", "deterministic"),
        }
    return None


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------


@dataclass
class ProvenanceCoverageTracker:
    """Deterministic provenance-chain auditor.

    Stateless — one instance handles many runs.

    Options
    -------
    strict_generative_evidence : bool, default False
        When True, also require ``evidence_sources`` on records whose
        ``origin == 'generative'``. When False (default), generative
        records get a pass on EVIDENCE_RESOLVABILITY so a narrative
        claim doesn't need to re-cite evidence its parent already
        cited. Matches the project convention used by
        ``MCPPersistenceHook``.
    """

    strict_generative_evidence: bool = False

    def audit(
        self,
        records: Iterable[Any],
        *,
        correlation_id: str = "",
    ) -> ProvenanceCoverageReport:
        """Produce a ``ProvenanceCoverageReport`` from a record set.

        The records iterable may mix ``ProvenanceRecord`` instances
        and plain dicts; both are normalized via ``_as_record_dict``.
        Items that fail normalization are silently skipped — the
        tracker is deterministic about what it *can* read, not about
        what it cannot.
        """

        records_list: list[dict[str, Any]] = []
        for r in records:
            norm = _as_record_dict(r)
            if norm is not None:
                records_list.append(norm)

        if not records_list:
            return self._empty_report(correlation_id)

        # Restrict to the requested correlation_id if provided (callers
        # sometimes pass the full store; we only audit the matching run).
        if correlation_id:
            records_list = [
                r for r in records_list if str(r.get("correlation_id", "")) == correlation_id
            ]

        if not records_list:
            return self._empty_report(correlation_id)

        id_set = {str(r["claim_id"]) for r in records_list}

        dim_offenders: dict[ProvenanceDimension, list[str]] = {d: [] for d in ALL_DIMENSIONS}
        for r in records_list:
            cid = str(r["claim_id"])
            if not str(r.get("rule_id", "")).strip():
                dim_offenders[ProvenanceDimension.RULE_ID].append(cid)
            if not str(r.get("generating_agent", "")).strip():
                dim_offenders[ProvenanceDimension.AGENT_ATTRIBUTION].append(cid)
            parent = str(r.get("parent_claim_id", "")).strip()
            if parent and parent not in id_set:
                dim_offenders[ProvenanceDimension.CHAIN_COMPLETENESS].append(cid)
            # evidence check — skip generative unless strict mode
            origin = str(r.get("origin", "deterministic"))
            must_check_evidence = origin != "generative" or self.strict_generative_evidence
            if must_check_evidence and not list(r.get("evidence_sources") or []):
                dim_offenders[ProvenanceDimension.EVIDENCE_RESOLVABILITY].append(cid)

        states: dict[ProvenanceDimension, DimensionState] = {}
        reasons: dict[ProvenanceDimension, str] = {}
        for dim in ALL_DIMENSIONS:
            offenders = dim_offenders[dim]
            if offenders:
                states[dim] = DimensionState.MISSING
                reasons[dim] = f"{len(offenders)}/{len(records_list)} record(s) missing {dim.value}"
            else:
                states[dim] = DimensionState.COVERED
                reasons[dim] = f"all {len(records_list)} record(s) carry {dim.value}"

        return ProvenanceCoverageReport(
            correlation_id=correlation_id or str(records_list[0].get("correlation_id", "")),
            total_records=len(records_list),
            dimension_states=MappingProxyType(states),
            offenders=MappingProxyType({d: tuple(dim_offenders[d]) for d in ALL_DIMENSIONS}),
            reasons=MappingProxyType(reasons),
        )

    @staticmethod
    def _empty_report(correlation_id: str) -> ProvenanceCoverageReport:
        """Coverage report for a run with no records.

        An empty provenance set isn't *complete* — there's nothing to
        attribute. Every dimension is MISSING with a diagnostic.
        """

        states = {d: DimensionState.MISSING for d in ALL_DIMENSIONS}
        offenders = {d: () for d in ALL_DIMENSIONS}
        reasons = {d: "no provenance records for this correlation_id" for d in ALL_DIMENSIONS}
        return ProvenanceCoverageReport(
            correlation_id=correlation_id,
            total_records=0,
            dimension_states=MappingProxyType(states),
            offenders=MappingProxyType(offenders),
            reasons=MappingProxyType(reasons),
        )


__all__ = [
    "ProvenanceDimension",
    "DimensionState",
    "ALL_DIMENSIONS",
    "ProvenanceCoverageReport",
    "ProvenanceCoverageTracker",
]
