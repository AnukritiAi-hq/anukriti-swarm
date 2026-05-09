"""``MCPVerificationLog`` — per-check verification audit log.

The other MCP services flatten verification into a single scalar
(``verification_state`` on memory records, ``verification_verdict`` on
provenance records). That's enough for filtering but loses the
per-check breakdown the ``verification/engine.py`` actually produces:
six independent checks (``evidence_grounding``,
``deterministic_boundary``, ``provenance``, ``guideline_conflict``,
``sparse_population``, ``hallucination_hooks``), each with its own
verdict + reason.

This service owns the ``verification_logs`` collection: **one document
per check per run** (not one per run). That means queries like
"show me every run where ``sparse_population`` warned" or "how often
does ``evidence_grounding`` fail on SAS queries" are cheap field
filters — no post-filtering arrays of nested docs.

Document shape
--------------

    {
      "_id":            <backend-assigned>,
      "correlation_id": "abc123…",
      "gene":           "CYP2C19",          # denormalized for easy filtering
      "drug":           "clopidogrel",      # denormalized
      "population":     "SAS",              # denormalized
      "run_label":      "single",           # e.g. "pop=AFR" in comparative runs
      "check_name":     "sparse_population",
      "verdict":        "warn",             # pass | warn | fail
      "reason":         "Only 12 samples for SAS",
      "overall_verdict":"warn",
      "overall_confidence": 0.82,
      "confidence_level":  "moderate",
      "escalation_tier":   "autonomous",
      "escalation_action": "",
      "logged_at":      "2026-05-09T02:40:11+00:00"
    }

Tools registered:
  verification.record          append a full run's verification report
                               (explodes into one row per check)
  verification.for_run         every check-row for a correlation_id
  verification.recent          N most recent check rows
  verification.failures        every row with verdict in {warn,fail},
                               filterable by check_name / gene / population
  verification.stats           rollup: pass/warn/fail counts per check

The ``record`` API accepts the raw ``run["verification"]`` dict the
orchestrator emits (see ``workflows/nodes.py:node_verification``), so
callers never have to reshape data manually — they just pass what
the pipeline already produces.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from integrations.mcp.client import MCPClient
from integrations.mcp.models import MCPOrigin, MCPToolResult


VERIFICATION_LOG_COLLECTION = "verification_logs"


# ---------------------------------------------------------------------------
# Canonical verdicts
# ---------------------------------------------------------------------------

# The engine emits "pass" / "warn" / "fail". We lowercase on ingest so
# downstream filter logic doesn't have to worry about casing.
_FAIL_TOKENS = {"fail", "failed"}
_WARN_TOKENS = {"warn", "warning"}
_PASS_TOKENS = {"pass", "passed"}


def _canon_verdict(raw: Any) -> str:
    """Normalize a verdict string to canonical lowercase form."""
    s = str(raw or "").strip().lower()
    if s in _FAIL_TOKENS:
        return "fail"
    if s in _WARN_TOKENS:
        return "warn"
    if s in _PASS_TOKENS:
        return "pass"
    return s or "pending"


@dataclass
class MCPVerificationLog:
    """Per-check verification audit log.

    Typical wiring::

        client = MCPClient()
        vlog = MCPVerificationLog(client)
        vlog.record_run(
            correlation_id=cid,
            verification=run["verification"],   # dict from workflows/nodes.py
            gene="CYP2C19", drug="clopidogrel", population="SAS",
        )
    """

    client: MCPClient
    collection: str = VERIFICATION_LOG_COLLECTION

    def __post_init__(self) -> None:
        self._register()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _register(self) -> None:
        r = self.client.registry
        r.register(
            "verification.record",
            self._tool_record,
            description=(
                "Log one run's verification report as one row per check."
            ),
            origin=MCPOrigin.ORCHESTRATOR,
            override=True,
        )
        r.register(
            "verification.for_run",
            self._tool_for_run,
            description="All verification check-rows for a correlation_id.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "verification.recent",
            self._tool_recent,
            description="N most recent verification check rows.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "verification.failures",
            self._tool_failures,
            description=(
                "Every check row with verdict in {warn,fail}, filterable by "
                "check_name / gene / population."
            ),
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "verification.stats",
            self._tool_stats,
            description="Pass/warn/fail counts per check_name.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )

    # ------------------------------------------------------------------
    # Python API
    # ------------------------------------------------------------------

    def record_run(
        self,
        *,
        correlation_id: str,
        verification: dict[str, Any],
        gene: str = "",
        drug: str = "",
        population: str = "",
        run_label: str = "single",
    ) -> MCPToolResult:
        """Persist one run's verification report.

        Accepts the exact shape ``workflows/nodes.py:node_verification``
        emits (``verdict`` / ``confidence`` / ``checks`` / …).
        """
        return self.client.invoke(
            "verification.record",
            args={
                "correlation_id": correlation_id,
                "verification": verification or {},
                "gene": gene,
                "drug": drug,
                "population": population,
                "run_label": run_label,
            },
            correlation_id=correlation_id,
            called_by="MCPVerificationLog",
            origin=MCPOrigin.ORCHESTRATOR,
        )

    def for_run(self, correlation_id: str) -> MCPToolResult:
        return self.client.invoke(
            "verification.for_run",
            args={"correlation_id": correlation_id},
            correlation_id=correlation_id,
            called_by="MCPVerificationLog",
        )

    def recent(self, limit: int = 20) -> MCPToolResult:
        return self.client.invoke(
            "verification.recent",
            args={"limit": limit},
            called_by="MCPVerificationLog",
        )

    def failures(
        self,
        *,
        check_name: str = "",
        gene: str = "",
        population: str = "",
        limit: int = 50,
    ) -> MCPToolResult:
        return self.client.invoke(
            "verification.failures",
            args={
                "check_name": check_name,
                "gene": gene,
                "population": population,
                "limit": limit,
            },
            called_by="MCPVerificationLog",
        )

    def stats(self) -> MCPToolResult:
        return self.client.invoke(
            "verification.stats",
            args={},
            called_by="MCPVerificationLog",
        )

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _tool_record(
        self,
        correlation_id: str,
        verification: dict[str, Any],
        gene: str = "",
        drug: str = "",
        population: str = "",
        run_label: str = "single",
    ) -> dict[str, Any]:
        """Explode one verification report into per-check rows.

        Returns a summary dict: ``{"rows_inserted": N, "overall": "pass"}``.
        If the report carries no checks (rare, but possible on error
        paths) a single placeholder row is recorded so the run is still
        queryable.
        """
        if not correlation_id:
            raise ValueError("verification.record requires correlation_id")
        if not isinstance(verification, dict):
            raise TypeError("verification.record expects a dict payload")

        overall_verdict = _canon_verdict(verification.get("verdict"))
        overall_conf = float(verification.get("confidence") or 0.0)
        confidence_level = str(verification.get("confidence_level") or "unknown")
        escalation_tier = str(verification.get("escalation_tier") or "autonomous")
        escalation_action = str(verification.get("action") or "")
        logged_at = datetime.now(timezone.utc).isoformat()

        checks = list(verification.get("checks") or [])
        rows: list[dict[str, Any]] = []

        if not checks:
            # Preserve the overall verdict even if checks are absent so
            # ``for_run`` always returns at least one row.
            rows.append(
                {
                    "correlation_id": correlation_id,
                    "gene": gene,
                    "drug": drug,
                    "population": population,
                    "run_label": run_label,
                    "check_name": "(aggregate)",
                    "verdict": overall_verdict,
                    "reason": "no per-check breakdown was emitted",
                    "overall_verdict": overall_verdict,
                    "overall_confidence": overall_conf,
                    "confidence_level": confidence_level,
                    "escalation_tier": escalation_tier,
                    "escalation_action": escalation_action,
                    "logged_at": logged_at,
                }
            )
        else:
            for c in checks:
                if not isinstance(c, dict):
                    continue
                rows.append(
                    {
                        "correlation_id": correlation_id,
                        "gene": gene,
                        "drug": drug,
                        "population": population,
                        "run_label": run_label,
                        "check_name": str(c.get("name") or ""),
                        "verdict": _canon_verdict(c.get("verdict")),
                        "reason": str(c.get("reason") or ""),
                        "overall_verdict": overall_verdict,
                        "overall_confidence": overall_conf,
                        "confidence_level": confidence_level,
                        "escalation_tier": escalation_tier,
                        "escalation_action": escalation_action,
                        "logged_at": logged_at,
                    }
                )

        inserted = 0
        for row in rows:
            self.client.backend.insert(self.collection, row)
            inserted += 1

        return {
            "rows_inserted": inserted,
            "overall": overall_verdict,
            "correlation_id": correlation_id,
        }

    def _tool_for_run(self, correlation_id: str) -> list[dict[str, Any]]:
        if not correlation_id:
            raise ValueError("verification.for_run requires correlation_id")
        return self.client.backend.query(
            self.collection,
            {"correlation_id": correlation_id},
            sort=[("logged_at", 1)],  # chronological within the run
        )

    def _tool_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.client.backend.query(
            self.collection, None, sort=[("logged_at", -1)], limit=int(limit)
        )

    def _tool_failures(
        self,
        check_name: str = "",
        gene: str = "",
        population: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return every warn/fail row matching the filter axes.

        Implementation note: the in-memory backend's minimal query
        language supports field equality and sort, so we pull the base
        slice server-side and filter warn/fail here. Mongo side could
        shortcut with ``{"verdict": {"$in": ["warn","fail"]}}`` — keeping
        both backends uniform is worth the extra ~10µs per query.
        """
        filter_: dict[str, Any] = {}
        if check_name:
            filter_["check_name"] = check_name
        if gene:
            filter_["gene"] = gene
        if population:
            filter_["population"] = population

        rows = self.client.backend.query(
            self.collection, filter_ or None, sort=[("logged_at", -1)]
        )
        hits = [r for r in rows if r.get("verdict") in ("warn", "fail")]
        return hits[: int(limit)]

    def _tool_stats(self) -> dict[str, Any]:
        """Aggregate pass/warn/fail counts per check_name."""
        rows = self.client.backend.query(self.collection, None)
        by_check: dict[str, dict[str, int]] = {}
        for r in rows:
            name = str(r.get("check_name") or "(unknown)")
            bucket = by_check.setdefault(
                name, {"pass": 0, "warn": 0, "fail": 0, "other": 0}
            )
            v = r.get("verdict") or ""
            if v in bucket:
                bucket[v] += 1
            else:
                bucket["other"] += 1
        return {
            "total_rows": len(rows),
            "by_check": by_check,
        }


__all__ = [
    "MCPVerificationLog",
    "VERIFICATION_LOG_COLLECTION",
]
