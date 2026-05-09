"""``MCPRetrieval`` — unified retrieval + replay across all MCP services.

Each individual service (``memory``, ``trace_store``, ``context_manager``,
``provenance``, ``evidence``) exposes its own tools. Most application
code only needs a handful of composed queries:

    - "give me the full picture for this correlation_id"
    - "has this patient's (gene, population) been analyzed before?"
    - "what evidence have we cited for this drug across runs?"
    - "replay workflow X — I want the context + trace back"

This module wires the five services together so callers don't have to
manage them individually. It does **not** open a new backend
connection; it's a pure aggregator over an existing ``MCPClient``.

Public surface
--------------

    retrieval = MCPRetrieval(client)       # services auto-constructed
    retrieval.lookup(correlation_id)       # bundled memory/trace/context/provenance
    retrieval.lookup_prior(gene, population, drug)   # prior executions
    retrieval.search_evidence(query, **filters)
    retrieval.population_history(population, limit)
    retrieval.replay(correlation_id)       # ReplayBundle for reconstruction

Replay contract
---------------

``replay(correlation_id)`` returns a ``ReplayBundle`` — a read-only view
onto everything we persisted about a run. The bundle's
``restore_context()`` method calls the context manager's restore path
to rehydrate the full ``SwarmExecutionContext``, which is enough for
downstream code to re-inspect the run without re-executing it. (Actual
re-execution is the orchestrator's job; the MCP layer only provides
the raw materials.)

Thread-safety
-------------
All services are stateless except for their registered tool handlers,
and the shared backend is assumed not to be written to concurrently
from multiple threads. This module does not add any new shared state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from integrations.mcp.client import MCPClient
from integrations.mcp.context_manager import MCPContextManager
from integrations.mcp.evidence import MCPEvidenceCache
from integrations.mcp.memory import MCPExecutionMemory
from integrations.mcp.provenance import MCPProvenanceStore
from integrations.mcp.trace_store import MCPTraceStore
from integrations.mcp.verification_log import MCPVerificationLog


# ---------------------------------------------------------------------------
# Bundled views
# ---------------------------------------------------------------------------


@dataclass
class RunLookup:
    """Everything persisted about a single correlation_id, already joined.

    Any field may be ``None`` / empty if the corresponding service never
    saw this run (e.g. a test execution that stored only the trace).
    """

    correlation_id: str
    memory: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    trace: dict[str, Any] | None = None
    provenance: list[dict[str, Any]] = field(default_factory=list)
    verification: list[dict[str, Any]] = field(default_factory=list)

    @property
    def exists(self) -> bool:
        """True if any service has a record for this correlation_id."""
        return any(
            [
                self.memory is not None,
                self.context is not None,
                self.trace is not None,
                bool(self.provenance),
                bool(self.verification),
            ]
        )

    def summary(self) -> dict[str, Any]:
        """One-line summary for dashboards / debugging."""
        return {
            "correlation_id": self.correlation_id,
            "has_memory": self.memory is not None,
            "has_context": self.context is not None,
            "has_trace": self.trace is not None,
            "provenance_claims": len(self.provenance),
            "verification_rows": len(self.verification),
        }


@dataclass
class ReplayBundle:
    """Materials needed to replay an orchestration run.

    The MCP layer doesn't run the orchestrator itself — it just hands
    back the frozen inputs/outputs. Callers (tests, debuggers, the
    ``demos/mcp_infrastructure_demo.py``) use the bundle to:

        - inspect a past run without touching the pipeline
        - re-ingest the context into a new orchestrator for "what-if"
          exploration (with ``restore_context``)
        - validate that provenance still resolves to stored evidence
    """

    lookup: RunLookup
    evidence_by_source: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Back-reference so ``restore_context`` can reach the context manager
    # without re-instantiating services.
    _client: MCPClient | None = None

    @property
    def correlation_id(self) -> str:
        return self.lookup.correlation_id

    def restore_context(self) -> Any:
        """Rehydrate the full ``SwarmExecutionContext`` for this run.

        Returns ``None`` when no context snapshot was stored. The real
        Pydantic model when ``core.orchestrator.context`` is importable
        (default), else the raw dict form.
        """
        if self._client is None:
            return None
        cm = MCPContextManager(self._client)
        result = cm.restore(self.correlation_id)
        return result.data if result.success else None


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


@dataclass
class MCPRetrieval:
    """Unified retrieval + replay API across all MCP services.

    Services are constructed once on init (``override=True`` keeps it
    idempotent even if other code already wired them to the client).
    All lookups return plain dicts / dataclasses — nothing held in
    memory between calls except the service references.
    """

    client: MCPClient

    def __post_init__(self) -> None:
        # Each service's __post_init__ registers its tools with
        # override=True, so re-instantiating is safe.
        self.memory = MCPExecutionMemory(client=self.client)
        self.traces = MCPTraceStore(client=self.client)
        self.contexts = MCPContextManager(client=self.client)
        self.provenance = MCPProvenanceStore(client=self.client)
        self.evidence = MCPEvidenceCache(client=self.client)
        self.verification = MCPVerificationLog(client=self.client)

    # ------------------------------------------------------------------
    # Single-run lookup
    # ------------------------------------------------------------------

    def lookup(self, correlation_id: str) -> RunLookup:
        """Fetch memory + context + trace + provenance + verification for one run."""
        if not correlation_id:
            raise ValueError("lookup requires correlation_id")
        mem = self.memory.get_run(correlation_id)
        ctx = self.contexts.load(correlation_id)
        trc = self.traces.get_trace(correlation_id)
        prov = self.provenance.for_run(correlation_id)
        vlog = self.verification.for_run(correlation_id)
        return RunLookup(
            correlation_id=correlation_id,
            memory=mem.data if mem.success else None,
            context=ctx.data if ctx.success else None,
            trace=trc.data if trc.success else None,
            provenance=list(prov.data or []) if prov.success else [],
            verification=list(vlog.data or []) if vlog.success else [],
        )

    # ------------------------------------------------------------------
    # Prior-execution search
    # ------------------------------------------------------------------

    def lookup_prior(
        self,
        *,
        gene: str = "",
        drug: str = "",
        population: str = "",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Return past run summaries matching the given axes.

        At least one of ``gene`` / ``drug`` / ``population`` must be
        supplied. Results come from the execution memory collection
        (not from traces) because memory is the authoritative run-level
        summary.
        """
        if not (gene or drug or population):
            raise ValueError(
                "lookup_prior requires at least one of gene/drug/population"
            )
        res = self.memory.find_runs(
            gene=gene, drug=drug, population=population, limit=limit
        )
        return list(res.data or []) if res.success else []

    # ------------------------------------------------------------------
    # Evidence search (simple passthrough + ergonomic filter)
    # ------------------------------------------------------------------

    def search_evidence(
        self,
        query: str = "",
        *,
        gene: str = "",
        drug: str = "",
        population: str = "",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        res = self.evidence.search(
            query=query, gene=gene, drug=drug, population=population, limit=limit
        )
        return list(res.data or []) if res.success else []

    # ------------------------------------------------------------------
    # Population / cohort history
    # ------------------------------------------------------------------

    def population_history(
        self, population: str, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Every run touching this population, newest first.

        Handy for the comparative narrative generator and for the
        ``dashboards/cli_dashboard.py`` population tab.
        """
        if not population:
            raise ValueError("population_history requires population")
        res = self.memory.find_runs(population=population, limit=limit)
        return list(res.data or []) if res.success else []

    # ------------------------------------------------------------------
    # Verification history
    # ------------------------------------------------------------------

    def verification_history_for_check(
        self,
        check_name: str,
        *,
        gene: str = "",
        population: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """All warn/fail rows for a named verification check.

        Thin wrapper around ``MCPVerificationLog.failures`` filtered by
        ``check_name``. Useful for questions like "which runs failed
        evidence_grounding?" or "when did sparse_population warn on
        SAS?".
        """
        if not check_name:
            raise ValueError("verification_history_for_check requires check_name")
        res = self.verification.failures(
            check_name=check_name, gene=gene, population=population, limit=limit
        )
        return list(res.data or []) if res.success else []

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    def replay(self, correlation_id: str) -> ReplayBundle:
        """Bundle everything needed to replay a run.

        Assembles:
          - the joined ``RunLookup`` view
          - a pre-resolved ``evidence_by_source`` map so callers don't
            have to chase PMIDs individually
        Returns a ``ReplayBundle`` whose ``restore_context`` yields the
        live ``SwarmExecutionContext``.
        """
        view = self.lookup(correlation_id)

        # Resolve every distinct evidence source referenced by either
        # the context or the provenance records, so consumers get one
        # coherent view.
        source_ids: set[str] = set()
        if view.context:
            for cit in view.context.get("evidence_refs") or []:
                if isinstance(cit, str):
                    source_ids.add(cit)
        for rec in view.provenance:
            for src in rec.get("evidence_sources") or []:
                if isinstance(src, str):
                    source_ids.add(src)

        evidence_by_source: dict[str, dict[str, Any]] = {}
        for sid in sorted(source_ids):
            hit = self.evidence.get(sid)
            if hit.success and hit.data:
                evidence_by_source[sid] = hit.data

        return ReplayBundle(
            lookup=view,
            evidence_by_source=evidence_by_source,
            _client=self.client,
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def service_summary(self) -> dict[str, int]:
        """Return the current row-count per collection.

        Cheap enough to call on every dashboard render; backed by
        ``backend.count`` so it works uniformly against Mongo and the
        in-memory backend.
        """
        b = self.client.backend
        return {
            "executions": b.count("executions"),
            "traces": b.count("traces"),
            "contexts": b.count("contexts"),
            "provenance": b.count("provenance"),
            "evidence": b.count("evidence"),
            "verification_logs": b.count("verification_logs"),
        }


__all__ = ["MCPRetrieval", "RunLookup", "ReplayBundle"]
