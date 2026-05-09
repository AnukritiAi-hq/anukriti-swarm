"""``EvidenceGroundingEngine`` — grounds claims against the MCP evidence cache.

Second layer of the deterministic safety engine. Where
``BiomedicalClaimValidator`` checks that each claim *names* an
evidence id, this engine checks that the named ids actually
*resolve* to a real biomedical passage in the MCP evidence cache.

The split is deliberate:

  - The claim validator is pure and fast (no IO).
  - The grounding engine touches MCP (``evidence.get`` tool) and
    runs second, enriching traces the validator already produced.

Why not collapse them? Because the claim validator is the front
line — it catches "you forgot to cite" in O(1) per claim even
when MCP is offline. The grounding engine catches the subtler
"you cited something that doesn't exist" only when MCP is live.
Tests can exercise the validator without an MCPClient at all.

Outputs
-------
``ground_claim(claim_trace)`` returns a **new** ``VerificationTrace``
with the same identity (claim_id preserved) but with the state
possibly demoted:

    trace.state=pass  + all refs resolve  → pass, reason carries
                                            "N/N sources resolved"
    trace.state=pass  + some refs missing → warn, downgrade
                                            "K/N sources resolved"
    trace.state=pass  + zero refs resolve → fail, hard downgrade
                                            "0/N sources resolved"
    trace.state=fail  → passthrough (already failed earlier)

Grounding only operates on claims that *already passed* the
mapping check — a claim the validator FAILed doesn't need a
second opinion; its problems are earlier in the pipeline.

``ground_traces(traces)`` applies ``ground_claim`` to a list.

``ground_run(run)`` is a convenience: validate + ground in one
call. Useful for the demo and for the VerificationAgent refactor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.verification.claim_validator import BiomedicalClaimValidator
from core.verification.trace import VerificationTrace, make_trace
from integrations.mcp.client import MCPClient
from integrations.mcp.evidence import MCPEvidenceCache


@dataclass
class GroundingReport:
    """Aggregate summary of a grounding pass.

    Populated alongside the per-claim traces. Useful for dashboards
    and for the escalation workflow (e.g. "if coverage < 50%,
    request additional evidence").
    """

    claims_total: int = 0
    claims_fully_grounded: int = 0
    claims_partially_grounded: int = 0
    claims_unresolved: int = 0
    sources_requested: int = 0
    sources_resolved: int = 0
    missing_source_ids: tuple[str, ...] = ()

    @property
    def coverage(self) -> float:
        """Fraction of requested sources that resolved, [0.0, 1.0]."""
        if self.sources_requested == 0:
            return 1.0  # nothing to ground = vacuously fully grounded
        return round(self.sources_resolved / self.sources_requested, 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claims_total": self.claims_total,
            "claims_fully_grounded": self.claims_fully_grounded,
            "claims_partially_grounded": self.claims_partially_grounded,
            "claims_unresolved": self.claims_unresolved,
            "sources_requested": self.sources_requested,
            "sources_resolved": self.sources_resolved,
            "coverage": self.coverage,
            "missing_source_ids": list(self.missing_source_ids),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


@dataclass
class EvidenceGroundingEngine:
    """Resolve claim citations against the MCP evidence cache.

    One instance wraps one ``MCPClient``; usage::

        engine = EvidenceGroundingEngine(MCPClient())
        grounded, report = engine.ground_run(run, correlation_id=cid)

    Can be used standalone (without the claim validator) by calling
    ``ground_traces(...)`` with pre-built traces.
    """

    client: MCPClient
    validator: BiomedicalClaimValidator = field(
        default_factory=BiomedicalClaimValidator
    )

    def __post_init__(self) -> None:
        # The evidence cache auto-registers its 6 MCP tools on the
        # shared registry if they aren't already registered. Idempotent.
        self.cache = MCPEvidenceCache(client=self.client)
        # Per-run resolution cache so repeat lookups in a single pass
        # don't re-invoke the MCP tool. Keyed by source_id.
        self._resolution_cache: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ground_run(
        self, run: dict[str, Any], *, correlation_id: str = ""
    ) -> tuple[list[VerificationTrace], GroundingReport]:
        """Validate and ground every claim in a single run."""
        traces = self.validator.validate_run(run, correlation_id=correlation_id)
        return self.ground_traces(traces)

    def ground_traces(
        self, traces: list[VerificationTrace]
    ) -> tuple[list[VerificationTrace], GroundingReport]:
        """Ground a list of pre-built traces; return new traces + report."""
        self._resolution_cache.clear()
        out: list[VerificationTrace] = []
        report = GroundingReport()
        missing: set[str] = set()

        for tr in traces:
            report.claims_total += 1
            grounded = self.ground_claim(tr)
            out.append(grounded)

            # Derive counters from the *grounded* trace's reason / state.
            n_requested = len(tr.evidence_refs)
            n_resolved = self._count_resolved(tr.evidence_refs)
            report.sources_requested += n_requested
            report.sources_resolved += n_resolved

            if n_requested == 0:
                # No citations to check → neither grounded nor unresolved;
                # claims-with-no-citations status is the claim validator's
                # job, not the grounding engine's. Count as "fully" to
                # avoid double-failing here.
                report.claims_fully_grounded += 1
            elif n_resolved == n_requested:
                report.claims_fully_grounded += 1
            elif n_resolved == 0:
                report.claims_unresolved += 1
            else:
                report.claims_partially_grounded += 1

            for sid in tr.evidence_refs:
                if not self._resolution_cache.get(sid, False):
                    missing.add(sid)

        report.missing_source_ids = tuple(sorted(missing))
        return out, report

    def ground_claim(self, trace: VerificationTrace) -> VerificationTrace:
        """Resolve one trace's evidence_refs; return a new trace.

        Preserves claim_id so downstream consumers can join the
        pre-grounding and post-grounding views.
        """
        # Already-failed claims passthrough unchanged — no need to
        # double-fail them, they already have escalation attached.
        if trace.failed:
            return trace

        refs = trace.evidence_refs
        if not refs:
            # No citations at all. Claim validator's job, not ours.
            return trace

        resolved = [sid for sid in refs if self._resolve(sid)]
        n_resolved = len(resolved)
        n_requested = len(refs)

        if n_resolved == n_requested:
            # Full grounding — keep state, enrich the reason.
            new_reason = (
                f"{trace.reason}; grounding: {n_resolved}/{n_requested} "
                f"source(s) resolved in MCP"
            )
            return _rebuild(trace, state=trace.state, reason=new_reason)

        if n_resolved == 0:
            # Zero grounding — hard fail. Citations present but none
            # land in MCP → the evidence layer has no idea what
            # we're talking about. That's unsafe.
            return _rebuild(
                trace,
                state="fail",
                reason=(
                    f"Grounding failure: 0/{n_requested} cited source(s) "
                    f"resolved in MCP evidence cache; "
                    f"missing: {', '.join(refs)}"
                ),
            )

        # Partial grounding — demote to warn.
        missing_list = [sid for sid in refs if sid not in resolved]
        return _rebuild(
            trace,
            state="warn",
            reason=(
                f"Partial grounding: {n_resolved}/{n_requested} source(s) "
                f"resolved; missing: {', '.join(missing_list)}"
            ),
        )

    # ------------------------------------------------------------------
    # MCP lookup
    # ------------------------------------------------------------------

    def _resolve(self, source_id: str) -> bool:
        """Return True when ``source_id`` resolves in the evidence cache."""
        if not source_id:
            return False
        cached = self._resolution_cache.get(source_id)
        if cached is not None:
            return cached
        try:
            res = self.cache.get(source_id)
        except Exception:
            # Treat lookup exceptions as misses — escalation workflow
            # will see a missing_source_id and request evidence.
            self._resolution_cache[source_id] = False
            return False
        ok = bool(res.success and res.data)
        self._resolution_cache[source_id] = ok
        return ok

    def _count_resolved(self, refs: tuple[str, ...]) -> int:
        """Count ``refs`` entries that resolved via ``_resolve``."""
        return sum(1 for sid in refs if self._resolve(sid))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rebuild(
    trace: VerificationTrace, *, state: str, reason: str
) -> VerificationTrace:
    """Return a new trace with state/reason updated; preserves claim_id."""
    return make_trace(
        claim=trace.claim,
        validator="EvidenceGroundingEngine",  # now the grounding engine
        state=state,
        confidence=trace.confidence,
        evidence_refs=trace.evidence_refs,
        escalation_events=trace.escalation_events,
        tier=trace.tier,
        reason=reason,
        correlation_id=trace.correlation_id,
        generating_agent=trace.generating_agent,
        rule_id=trace.rule_id,
        claim_id=trace.claim_id,  # critical — preserves identity across layers
    )


__all__ = ["EvidenceGroundingEngine", "GroundingReport"]
