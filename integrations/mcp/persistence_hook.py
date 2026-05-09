"""``MCPPersistenceHook`` — auto-persist orchestration runs into MCP.

One hook call after a ``GeminiOrchestrator.run(...)`` lands all of the
following into the backend:

  - ``memory.store``       run summary (gene, drug, population, verdict,
                           active_agents, evidence_refs, gemini_summary)
  - ``traces.store``       the full ``OrchestrationTrace``
  - ``context.snapshot``   the full ``SwarmExecutionContext``
  - ``provenance.record``  one record per deterministic finding + one
                           record per generative narrative
  - ``evidence.index``     every evidence source that appeared in the
                           run, so subsequent lookups hit the cache

Design
------
The hook is deliberately orthogonal to the orchestrator — it consumes
an ``OrchestrationResult`` (the orchestrator's return value) rather
than instrumenting the orchestrator itself. That keeps the orchestrator
unaware of persistence, and lets callers turn persistence on/off per
invocation:

    result = orchestrator.run(gene="CYP2C19", drug="clopidogrel", ...)
    hook = MCPPersistenceHook(client)
    report = hook.persist(result)

The hook never raises for partial failures — each sub-operation is
wrapped so the run summary lands even if, say, the evidence cache
rejects a duplicate source_id. A ``PersistenceReport`` is returned
so callers can surface "stored X but evidence indexing failed" in
demos / dashboards.

Provenance policy
-----------------
For every deterministic run (``result.coordination.runs``) the hook
records:

  1. A ``phenotype`` claim       (rule=cpic.activity_score)
  2. A ``recommendation`` claim  (rule=cpic.recommendation, parent=phenotype)
  3. Zero or more ``population`` claims (rule=hardy_weinberg, advisory)

For every generative narrative (``result.coordination.narratives``)
the hook records:

  4. A ``narrative`` claim (origin=generative, parent=recommendation,
     only persisted when the orchestrator's boundary allowed
     synthesis — i.e. verification_verdict ∈ {passed, warning}).

This keeps the claim chain consistent with the PROV-DM shape in
``integrations.mcp.provenance``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from integrations.mcp.client import MCPClient
from integrations.mcp.context_manager import MCPContextManager
from integrations.mcp.evidence import MCPEvidenceCache
from integrations.mcp.memory import MCPExecutionMemory
from integrations.mcp.provenance import MCPProvenanceStore, ProvenanceRecord
from integrations.mcp.trace_store import MCPTraceStore
from integrations.mcp.verification_log import MCPVerificationLog

if TYPE_CHECKING:  # pragma: no cover — type-checker only
    from agents.orchestrator.gemini_orchestrator import OrchestrationResult


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass
class PersistenceReport:
    """Outcome of one ``persist()`` call.

    Field booleans mirror the five services. ``claims_recorded`` counts
    provenance entries (one per deterministic finding + one per
    narrative). ``errors`` holds any exception messages encountered
    during the non-fatal sub-operations.
    """

    correlation_id: str
    memory_stored: bool = False
    trace_stored: bool = False
    context_stored: bool = False
    claims_recorded: int = 0
    evidence_indexed: int = 0
    verification_rows: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when the three core stores landed — evidence is best-effort."""
        return self.memory_stored and self.trace_stored and self.context_stored

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "memory_stored": self.memory_stored,
            "trace_stored": self.trace_stored,
            "context_stored": self.context_stored,
            "claims_recorded": self.claims_recorded,
            "evidence_indexed": self.evidence_indexed,
            "verification_rows": self.verification_rows,
            "ok": self.ok,
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# Hook
# ---------------------------------------------------------------------------


@dataclass
class MCPPersistenceHook:
    """Persist an ``OrchestrationResult`` across all MCP services.

    The hook owns no state between calls — construct one per client
    and reuse it. Services are instantiated with ``override=True``
    semantics so construction is idempotent.
    """

    client: MCPClient

    def __post_init__(self) -> None:
        self.memory = MCPExecutionMemory(client=self.client)
        self.traces = MCPTraceStore(client=self.client)
        self.contexts = MCPContextManager(client=self.client)
        self.provenance = MCPProvenanceStore(client=self.client)
        self.evidence = MCPEvidenceCache(client=self.client)
        self.verification = MCPVerificationLog(client=self.client)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def persist(self, result: "OrchestrationResult") -> PersistenceReport:
        """Persist everything about ``result`` into the backend."""
        ctx = result.context
        cid = ctx.correlation_id
        report = PersistenceReport(correlation_id=cid)

        self._store_memory(result, report)
        self._store_trace(result, report)
        self._store_context(result, report)
        self._record_provenance(result, report)
        self._index_evidence(result, report)
        self._log_verification(result, report)

        return report

    # ------------------------------------------------------------------
    # Step: run summary → memory
    # ------------------------------------------------------------------

    def _store_memory(
        self, result: "OrchestrationResult", report: PersistenceReport
    ) -> None:
        ctx = result.context
        try:
            record = {
                "correlation_id": ctx.correlation_id,
                "query": ctx.query,
                "gene": ctx.gene,
                "drug": ctx.drug,
                "population": ctx.population,
                "populations": list(ctx.populations),
                "drugs": list(ctx.drugs),
                "genotype": dict(ctx.genotype),
                "active_agents": list(ctx.active_agents),
                "evidence_refs": list(ctx.evidence_refs),
                "deterministic_summary": self._summarize_deterministic(result),
                "gemini_summary": dict(result.coordination.narratives or {}),
                "verification_state": ctx.verification_state.value,
                "phase": ctx.phase.value,
                "escalation_reason": result.coordination.escalation_reason,
                "total_duration_ms": result.total_duration_ms,
                "plan_origin": result.plan.origin,
                "plan_model": result.plan.model,
                "plan_steps": len(result.plan.steps),
                "errors": list(result.errors),
            }
            res = self.memory.store_run(record)
            report.memory_stored = res.success
            if not res.success:
                report.errors.append(f"memory.store: {res.error}")
        except Exception as exc:
            report.errors.append(f"memory.store: {exc}")

    @staticmethod
    def _summarize_deterministic(
        result: "OrchestrationResult",
    ) -> list[dict[str, Any]]:
        """Flatten each run's pharmacogene + population + first rec."""
        out: list[dict[str, Any]] = []
        for run in result.coordination.runs:
            pgx = run.get("pharmacogene_result") or {}
            pop = run.get("population_result") or {}
            recs = run.get("recommendations") or []
            out.append(
                {
                    "label": run.get("_row_label", "single"),
                    "gene": pgx.get("gene", "") or run.get("gene", ""),
                    "drug": run.get("drug", ""),
                    "population": pop.get("population")
                    or run.get("population", ""),
                    "phenotype": pgx.get("phenotype", ""),
                    "risk": pgx.get("risk", ""),
                    "frequency": pop.get("frequency"),
                    "recommendation": recs[0]["recommendation"] if recs else "",
                    "verification_verdict": (run.get("verification") or {}).get(
                        "verdict", ""
                    ),
                    "confidence": (run.get("verification") or {}).get("confidence"),
                }
            )
        return out

    # ------------------------------------------------------------------
    # Step: OrchestrationTrace → traces
    # ------------------------------------------------------------------

    def _store_trace(
        self, result: "OrchestrationResult", report: PersistenceReport
    ) -> None:
        try:
            trace = result.context.orchestration_trace
            if trace is None:
                report.errors.append("traces.store: trace missing on context")
                return
            res = self.traces.store_trace(trace)
            report.trace_stored = res.success
            if not res.success:
                report.errors.append(f"traces.store: {res.error}")
        except Exception as exc:
            report.errors.append(f"traces.store: {exc}")

    # ------------------------------------------------------------------
    # Step: SwarmExecutionContext → contexts
    # ------------------------------------------------------------------

    def _store_context(
        self, result: "OrchestrationResult", report: PersistenceReport
    ) -> None:
        try:
            res = self.contexts.snapshot(result.context)
            report.context_stored = res.success
            if not res.success:
                report.errors.append(f"context.snapshot: {res.error}")
        except Exception as exc:
            report.errors.append(f"context.snapshot: {exc}")

    # ------------------------------------------------------------------
    # Step: deterministic findings + narratives → provenance
    # ------------------------------------------------------------------

    def _record_provenance(
        self, result: "OrchestrationResult", report: PersistenceReport
    ) -> None:
        ctx = result.context
        cid = ctx.correlation_id

        for run in result.coordination.runs:
            pgx = run.get("pharmacogene_result") or {}
            pop = run.get("population_result") or {}
            verif = run.get("verification") or {}
            recs = run.get("recommendations") or []
            label = run.get("_row_label", "single")

            # citation sources appearing anywhere in the run
            sources = self._collect_sources(run, ctx.evidence_refs)

            # 1. Phenotype claim
            phenotype_claim_id = ""
            phenotype_text = self._phenotype_claim_text(pgx, run, pop)
            if phenotype_text:
                rec = ProvenanceRecord(
                    claim=phenotype_text,
                    generating_agent=f"pharmacogene_{(pgx.get('gene') or ctx.gene or '').lower()}",
                    rule_id="cpic.activity_score",
                    correlation_id=cid,
                    evidence_sources=sources,
                    verification_verdict=str(verif.get("verdict", "")).lower() or "pending",
                    confidence=float(verif.get("confidence", 1.0) or 1.0),
                    metadata={"label": label},
                )
                r = self.provenance.record(rec)
                if r.success:
                    report.claims_recorded += 1
                    phenotype_claim_id = r.data["claim_id"]
                else:
                    report.errors.append(f"provenance.record(phenotype): {r.error}")

            # 2. Recommendation claim (derived from phenotype)
            recommendation_claim_id = ""
            if recs:
                first = recs[0]
                rec_text = first.get("recommendation") or first.get("action") or ""
                if rec_text:
                    rec = ProvenanceRecord(
                        claim=rec_text,
                        generating_agent="orchestrator",
                        rule_id="cpic.recommendation",
                        correlation_id=cid,
                        evidence_sources=sources,
                        verification_verdict=str(verif.get("verdict", "")).lower() or "pending",
                        confidence=float(first.get("confidence") or verif.get("confidence") or 1.0),
                        parent_claim_id=phenotype_claim_id,
                        metadata={"label": label, "strength": first.get("strength")},
                    )
                    r = self.provenance.record(rec)
                    if r.success:
                        report.claims_recorded += 1
                        recommendation_claim_id = r.data["claim_id"]
                    else:
                        report.errors.append(f"provenance.record(rec): {r.error}")

            # 3. Population claim (advisory — Hardy-Weinberg estimate)
            if pop.get("frequency") is not None:
                freq = pop.get("frequency")
                pop_text = (
                    f"Frequency of {pgx.get('gene', ctx.gene)} phenotype in "
                    f"{pop.get('population', ctx.population)} ≈ {freq}"
                )
                rec = ProvenanceRecord(
                    claim=pop_text,
                    generating_agent=f"population_{(pop.get('population') or ctx.population or '').lower()}",
                    rule_id="hardy_weinberg",
                    correlation_id=cid,
                    evidence_sources=[],
                    verification_verdict="advisory",
                    confidence=float(pop.get("confidence") or 1.0),
                    metadata={"label": label},
                )
                r = self.provenance.record(rec)
                if r.success:
                    report.claims_recorded += 1

            # 4. Narratives — one claim per audience
            for audience, text in (result.coordination.narratives or {}).items():
                if not text:
                    continue
                rec = ProvenanceRecord(
                    claim=text,
                    generating_agent="gemini.orchestrator",
                    rule_id=f"narrative.{audience}",
                    correlation_id=cid,
                    evidence_sources=sources,
                    verification_verdict=ctx.verification_state.value,
                    confidence=float(verif.get("confidence") or 1.0),
                    parent_claim_id=recommendation_claim_id,
                    origin="generative",
                    metadata={"label": label, "audience": audience},
                )
                r = self.provenance.record(rec)
                if r.success:
                    report.claims_recorded += 1
                else:
                    report.errors.append(
                        f"provenance.record(narrative/{audience}): {r.error}"
                    )

    @staticmethod
    def _collect_sources(
        run: dict[str, Any], fallback_refs: list[str]
    ) -> list[str]:
        """Best-effort extraction of citation ids from a run + orchestrator ctx."""
        out: list[str] = []
        # From top-level citations list
        for cit in run.get("citations") or []:
            sid = cit.get("source_id") if isinstance(cit, dict) else cit
            if sid and sid not in out:
                out.append(sid)
        # From recommendations
        for rec in run.get("recommendations") or []:
            for cit in rec.get("citations") or []:
                sid = cit.get("source_id") if isinstance(cit, dict) else cit
                if sid and sid not in out:
                    out.append(sid)
        # Fallback: orchestrator-level refs
        for sid in fallback_refs or []:
            if sid not in out:
                out.append(sid)
        return out

    @staticmethod
    def _phenotype_claim_text(
        pgx: dict[str, Any], run: dict[str, Any], pop: dict[str, Any]
    ) -> str:
        """Build a human-readable phenotype claim string."""
        gene = pgx.get("gene") or run.get("gene") or ""
        phenotype = pgx.get("phenotype") or ""
        if not gene or not phenotype:
            return ""
        diplo = (run.get("allele1", ""), run.get("allele2", ""))
        if all(diplo):
            return f"{gene} {diplo[0]}/{diplo[1]} → {phenotype}"
        return f"{gene} → {phenotype}"

    # ------------------------------------------------------------------
    # Step: citations → evidence cache
    # ------------------------------------------------------------------

    def _index_evidence(
        self, result: "OrchestrationResult", report: PersistenceReport
    ) -> None:
        """Upsert every evidence citation encountered into the cache.

        Uses the citation's own dict fields when available (title,
        passage/content, guideline_source); falls back to empty
        strings otherwise. Re-indexing an existing source_id is safe
        because the cache does upsert semantics.
        """
        seen: set[str] = set()
        for run in result.coordination.runs:
            # Prefer top-level retrieval results (they carry passage + metadata).
            for rr in run.get("retrieval_results") or []:
                sid = rr.get("source_id") if isinstance(rr, dict) else ""
                if not sid or sid in seen:
                    continue
                seen.add(sid)
                try:
                    r = self.evidence.index(
                        source_id=sid,
                        content=rr.get("passage") or rr.get("content") or "",
                        gene=rr.get("gene") or run.get("gene") or "",
                        drug=rr.get("drug") or run.get("drug") or "",
                        population=rr.get("population") or "",
                        title=rr.get("title") or "",
                        guideline_source=(rr.get("metadata") or {}).get(
                            "guideline_source"
                        )
                        or "",
                        metadata=rr.get("metadata") or {},
                    )
                    if r.success:
                        report.evidence_indexed += 1
                    else:
                        report.errors.append(f"evidence.index({sid}): {r.error}")
                except Exception as exc:
                    report.errors.append(f"evidence.index({sid}): {exc}")

            # Also index bare citations (string ids or dicts) — still
            # useful for lookup even without a passage attached.
            for cit in run.get("citations") or []:
                if isinstance(cit, str):
                    sid = cit
                    title = ""
                    guideline_source = ""
                    metadata: dict[str, Any] = {}
                elif isinstance(cit, dict):
                    sid = cit.get("source_id") or ""
                    title = cit.get("title") or ""
                    guideline_source = cit.get("guideline_source") or ""
                    metadata = {
                        "year": cit.get("year"),
                        "evidence_level": cit.get("evidence_level"),
                    }
                else:
                    continue
                if not sid or sid in seen:
                    continue
                seen.add(sid)
                try:
                    r = self.evidence.index(
                        source_id=sid,
                        content=title or "(no passage cached)",
                        gene=run.get("gene") or "",
                        drug=run.get("drug") or "",
                        title=title,
                        guideline_source=guideline_source,
                        metadata=metadata,
                    )
                    if r.success:
                        report.evidence_indexed += 1
                except Exception as exc:
                    report.errors.append(f"evidence.index({sid}): {exc}")

    # ------------------------------------------------------------------
    # Step: per-check verification breakdown → verification_logs
    # ------------------------------------------------------------------

    def _log_verification(
        self, result: "OrchestrationResult", report: PersistenceReport
    ) -> None:
        """Explode each run's verification report into per-check rows.

        The memory + provenance records already carry the aggregate
        verdict + confidence; this step preserves the *per-check*
        breakdown (6 checks produced by ``verification/engine.py``) so
        callers can query "every run where ``sparse_population`` warned"
        without scanning full memory docs.

        Best-effort by design: a malformed verification dict yields a
        warning in ``report.errors`` but never blocks the run from
        landing in the other stores.
        """
        ctx = result.context
        cid = ctx.correlation_id

        for run in result.coordination.runs:
            verif = run.get("verification")
            if not isinstance(verif, dict) or not verif:
                # No verification stage ran for this row — skip silently.
                continue
            try:
                pgx = run.get("pharmacogene_result") or {}
                pop = run.get("population_result") or {}
                res = self.verification.record_run(
                    correlation_id=cid,
                    verification=verif,
                    gene=pgx.get("gene") or run.get("gene") or ctx.gene or "",
                    drug=run.get("drug") or ctx.drug or "",
                    population=pop.get("population")
                    or run.get("population")
                    or ctx.population
                    or "",
                    run_label=run.get("_row_label", "single"),
                )
                if res.success:
                    report.verification_rows += int(
                        (res.data or {}).get("rows_inserted", 0)
                    )
                else:
                    report.errors.append(f"verification.record: {res.error}")
            except Exception as exc:
                report.errors.append(f"verification.record: {exc}")


__all__ = ["MCPPersistenceHook", "PersistenceReport"]
