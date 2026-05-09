"""``ProvenanceValidator`` — cross-checks MCP provenance chain completeness.

Final layer of the engine stack. Where ``BiomedicalClaimValidator``
checks that each claim names evidence + rule + source + outcome,
``EvidenceGroundingEngine`` checks that named evidence resolves in
MCP, and ``SafetyConstraintEngine`` checks biomedical correctness,
this engine checks that the **persisted provenance trail** the
run left behind in ``MCPProvenanceStore`` is *complete and
internally consistent*.

Why a dedicated validator for this? Because the four fields the
brief names map to four *independent* persistence pathways:

    evidence_refs        MCPEvidenceCache.index
    rule_id              ProvenanceRecord.rule_id
    source reference     ProvenanceRecord.generating_agent +
                         ``rule_id`` namespace ('cpic.', 'hardy_weinberg')
    verification         ProvenanceRecord.verification_verdict
    outcome              populated by the persistence hook

A run can pass every in-memory check and still have a broken
provenance trail — e.g. the hook silently dropped a claim because
of a transient MCP failure, or the generating_agent field is
blank, or the parent_claim_id chain has a dangling link.

This validator runs *after* persistence (MCPPersistenceHook) and
audits the resulting records. It doesn't fix anything — it just
emits VerificationTraces flagging incomplete chains so the
EscalationWorkflow (commit 9) can downgrade or block.

Checks performed per run
------------------------

    chain_completeness
        Every claim in the run's provenance records should either
        be a root (no parent_claim_id) or have a parent that is
        also persisted in the same run. Dangling parents → FAIL.

    rule_id_coverage
        Every persisted ProvenanceRecord must carry a non-empty
        rule_id. Blank → FAIL. (The mapping is enforced on insert
        by MCPProvenanceStore.record, but we check the persisted
        set anyway to catch data-layer drift.)

    evidence_resolvability
        For each record's evidence_sources, verify the MCP
        evidence cache has that source_id. Same check as
        EvidenceGroundingEngine but run against the *persisted*
        state, catching the case where a claim was recorded but
        its evidence wasn't.

    agent_attribution
        Every record must have a non-empty generating_agent so
        the audit trail can answer "who produced this claim?".
        Blank → FAIL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.verification.trace import EscalationEvent, VerificationTrace, make_trace
from integrations.mcp.client import MCPClient
from integrations.mcp.evidence import MCPEvidenceCache
from integrations.mcp.provenance import MCPProvenanceStore


# ---------------------------------------------------------------------------
# Report shape
# ---------------------------------------------------------------------------


@dataclass
class ProvenanceReport:
    """Aggregate summary of a provenance validation pass."""

    correlation_id: str
    records_examined: int = 0
    records_with_missing_rule: int = 0
    records_with_missing_agent: int = 0
    records_with_unresolved_evidence: int = 0
    dangling_parents: tuple[str, ...] = ()   # claim_ids whose parent is missing
    missing_source_ids: tuple[str, ...] = ()

    @property
    def is_clean(self) -> bool:
        """True when every check passed."""
        return (
            self.records_with_missing_rule == 0
            and self.records_with_missing_agent == 0
            and self.records_with_unresolved_evidence == 0
            and not self.dangling_parents
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "records_examined": self.records_examined,
            "records_with_missing_rule": self.records_with_missing_rule,
            "records_with_missing_agent": self.records_with_missing_agent,
            "records_with_unresolved_evidence": (
                self.records_with_unresolved_evidence
            ),
            "dangling_parents": list(self.dangling_parents),
            "missing_source_ids": list(self.missing_source_ids),
            "is_clean": self.is_clean,
        }


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


@dataclass
class ProvenanceValidator:
    """MCP-backed provenance chain completeness validator.

    Wraps an ``MCPClient`` and uses the existing provenance + evidence
    services. Stateless between runs — call ``validate_run(cid)``
    as many times as needed.
    """

    client: MCPClient

    def __post_init__(self) -> None:
        # Attach the services we need. Both are idempotent —
        # re-construction with the same client is safe because
        # tool registration uses override=True.
        self.provenance = MCPProvenanceStore(client=self.client)
        self.evidence = MCPEvidenceCache(client=self.client)
        # Per-run resolution cache so the same source_id resolved
        # twice in the same pass only hits MCP once.
        self._evidence_cache: dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_run(
        self, correlation_id: str
    ) -> tuple[list[VerificationTrace], ProvenanceReport]:
        """Validate the provenance chain for one correlation_id.

        Fetches every ProvenanceRecord with this correlation_id from
        MCP, runs the 4 checks, and emits one VerificationTrace per
        detected issue. Returns ``([], clean_report)`` when
        everything is fine.

        When no provenance records exist for the correlation_id, a
        single 'fail' trace is returned flagging the gap — that's
        itself an audit failure (we ran but didn't persist).
        """
        if not correlation_id:
            raise ValueError("validate_run requires correlation_id")

        self._evidence_cache.clear()
        report = ProvenanceReport(correlation_id=correlation_id)
        records = self._fetch_records(correlation_id)
        report.records_examined = len(records)

        if not records:
            # No persistence happened. That *is* a provenance failure.
            trace = make_trace(
                claim="provenance chain exists for this run",
                validator="ProvenanceValidator",
                state="fail",
                confidence=0.0,
                evidence_refs=(),
                reason=(
                    f"No ProvenanceRecord landed in MCP for "
                    f"correlation_id={correlation_id!r}"
                ),
                correlation_id=correlation_id,
                generating_agent="provenance_validator",
                rule_id="provenance.completeness",
                escalation_events=(
                    EscalationEvent(
                        action="block",
                        reason="Empty provenance chain",
                        target="persistence_hook",
                    ),
                ),
            )
            return [trace], report

        # Index for parent-dangling detection.
        claim_ids: set[str] = {r.get("claim_id", "") for r in records}

        traces: list[VerificationTrace] = []
        dangling: list[str] = []
        missing_sources: set[str] = set()

        for rec in records:
            trace_list, counters = self._audit_record(rec, correlation_id, claim_ids)
            traces.extend(trace_list)
            report.records_with_missing_rule += counters["missing_rule"]
            report.records_with_missing_agent += counters["missing_agent"]
            report.records_with_unresolved_evidence += counters["unresolved_evidence"]
            dangling.extend(counters["dangling_parents"])
            missing_sources.update(counters["missing_sources"])

        report.dangling_parents = tuple(dangling)
        report.missing_source_ids = tuple(sorted(missing_sources))

        if report.is_clean:
            # Emit a single pass trace so audit consumers have
            # something positive to show — "provenance chain is
            # complete" is itself worth a log line.
            traces.append(
                make_trace(
                    claim=(
                        f"provenance chain for {correlation_id} is complete "
                        f"({report.records_examined} record(s))"
                    ),
                    validator="ProvenanceValidator",
                    state="pass",
                    confidence=1.0,
                    evidence_refs=(),
                    reason="Every record has rule_id + generating_agent; "
                    "parents resolve; evidence resolves",
                    correlation_id=correlation_id,
                    generating_agent="provenance_validator",
                    rule_id="provenance.completeness",
                )
            )

        return traces, report

    # ------------------------------------------------------------------
    # Per-record audit
    # ------------------------------------------------------------------

    def _audit_record(
        self,
        rec: dict[str, Any],
        cid: str,
        claim_ids: set[str],
    ) -> tuple[list[VerificationTrace], dict[str, Any]]:
        """Run the 4 checks against one persisted record."""
        traces: list[VerificationTrace] = []
        counters: dict[str, Any] = {
            "missing_rule": 0,
            "missing_agent": 0,
            "unresolved_evidence": 0,
            "dangling_parents": [],
            "missing_sources": set(),
        }

        claim = rec.get("claim", "")
        claim_id = rec.get("claim_id", "")
        rule_id = rec.get("rule_id", "")
        gen_agent = rec.get("generating_agent", "")
        parent = rec.get("parent_claim_id", "")
        evidence_sources = list(rec.get("evidence_sources") or [])

        # Check 1: rule_id coverage
        if not rule_id:
            counters["missing_rule"] = 1
            traces.append(
                self._fail(
                    claim=claim,
                    claim_id=claim_id,
                    rule_id="provenance.rule_id_coverage",
                    reason="Persisted record has empty rule_id",
                    correlation_id=cid,
                    target="provenance_store",
                )
            )

        # Check 2: agent attribution
        if not gen_agent:
            counters["missing_agent"] = 1
            traces.append(
                self._fail(
                    claim=claim,
                    claim_id=claim_id,
                    rule_id="provenance.agent_attribution",
                    reason="Persisted record has empty generating_agent",
                    correlation_id=cid,
                    target="provenance_store",
                )
            )

        # Check 3: chain completeness (no dangling parents)
        if parent and parent not in claim_ids:
            counters["dangling_parents"].append(claim_id)
            traces.append(
                self._fail(
                    claim=claim,
                    claim_id=claim_id,
                    rule_id="provenance.chain_completeness",
                    reason=(
                        f"parent_claim_id={parent!r} is not present among "
                        f"records for this run — dangling parent"
                    ),
                    correlation_id=cid,
                    target="provenance_store",
                )
            )

        # Check 4: evidence resolvability
        unresolved: list[str] = []
        for sid in evidence_sources:
            if not self._resolve(sid):
                unresolved.append(sid)
        if unresolved:
            counters["unresolved_evidence"] = 1
            counters["missing_sources"].update(unresolved)
            traces.append(
                self._warn(
                    claim=claim,
                    claim_id=claim_id,
                    rule_id="provenance.evidence_resolvability",
                    reason=(
                        f"Record cites {len(unresolved)}/{len(evidence_sources)} "
                        f"source(s) not indexed in MCP evidence cache: "
                        f"{', '.join(unresolved)}"
                    ),
                    correlation_id=cid,
                    evidence_refs=tuple(evidence_sources),
                )
            )

        return traces, counters

    # ------------------------------------------------------------------
    # MCP plumbing
    # ------------------------------------------------------------------

    def _fetch_records(self, correlation_id: str) -> list[dict[str, Any]]:
        res = self.provenance.for_run(correlation_id)
        if not res.success:
            return []
        return list(res.data or [])

    def _resolve(self, source_id: str) -> bool:
        if not source_id:
            return False
        cached = self._evidence_cache.get(source_id)
        if cached is not None:
            return cached
        try:
            r = self.evidence.get(source_id)
        except Exception:
            self._evidence_cache[source_id] = False
            return False
        ok = bool(r.success and r.data)
        self._evidence_cache[source_id] = ok
        return ok

    # ------------------------------------------------------------------
    # Trace factories
    # ------------------------------------------------------------------

    def _fail(
        self,
        *,
        claim: str,
        claim_id: str,
        rule_id: str,
        reason: str,
        correlation_id: str,
        target: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> VerificationTrace:
        return make_trace(
            claim=claim or "(empty claim)",
            validator="ProvenanceValidator",
            state="fail",
            confidence=0.0,
            evidence_refs=evidence_refs,
            escalation_events=(
                EscalationEvent(
                    action="downgrade",
                    reason=reason,
                    target=target,
                ),
            ),
            reason=reason,
            correlation_id=correlation_id,
            generating_agent="provenance_validator",
            rule_id=rule_id,
            claim_id=claim_id or "",
        )

    def _warn(
        self,
        *,
        claim: str,
        claim_id: str,
        rule_id: str,
        reason: str,
        correlation_id: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> VerificationTrace:
        return make_trace(
            claim=claim or "(empty claim)",
            validator="ProvenanceValidator",
            state="warn",
            confidence=0.5,
            evidence_refs=evidence_refs,
            reason=reason,
            correlation_id=correlation_id,
            generating_agent="provenance_validator",
            rule_id=rule_id,
            claim_id=claim_id or "",
        )


__all__ = [
    "ProvenanceValidator",
    "ProvenanceReport",
]
