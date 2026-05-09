"""In-memory cache for recent unified execution runs.

Phase 3, commit 7 of the Unified Orchestration + Visualization brief.

A small bounded LRU cache keyed by correlation_id. Stores both
the ``UnifiedExecutionReport`` (for ``/api/snapshot``) and the
ordered event stream (for ``/api/replay``).

Scope firewall
--------------
* Not a database. No disk persistence. Restart clears everything.
* Not multi-process-safe. Each uvicorn worker has its own cache;
  this is fine for the research / demo use case. Cross-worker
  replay requires an external store (MCP already provides that
  path; this cache is for the live UI only).
* Bounded — default 64 recent runs. Beyond that, oldest runs
  are evicted. Evidence persistence lives in MCP.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from core.runtime import RuntimeEvent, UnifiedExecutionReport


@dataclass
class CachedRun:
    """One run's complete live state."""

    report: UnifiedExecutionReport
    events: tuple[RuntimeEvent, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report": self.report.to_dict(),
            "events": [e.to_dict() for e in self.events],
        }


@dataclass
class RunCache:
    """Bounded LRU cache of ``CachedRun`` keyed by correlation_id."""

    max_entries: int = 64
    _items: "OrderedDict[str, CachedRun]" = field(default_factory=OrderedDict)

    def put(self, correlation_id: str, cached: CachedRun) -> None:
        """Insert or refresh an entry; evict oldest when full."""

        if not correlation_id:
            return
        if correlation_id in self._items:
            self._items.move_to_end(correlation_id)
        self._items[correlation_id] = cached
        while len(self._items) > self.max_entries:
            self._items.popitem(last=False)

    def get(self, correlation_id: str) -> CachedRun | None:
        """Return a run (and move to the MRU position) or None."""

        entry = self._items.get(correlation_id)
        if entry is not None:
            self._items.move_to_end(correlation_id)
        return entry

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return a compact summary of the N most-recent runs."""

        summaries: list[dict[str, Any]] = []
        for cid, cached in reversed(list(self._items.items())):
            if len(summaries) >= limit:
                break
            rep = cached.report
            summaries.append({
                "correlation_id": cid,
                "drug": rep.drug,
                "gene": rep.gene,
                "population": rep.population,
                "genotype": rep.genotype,
                "decision": (rep.evidence_sufficiency or {}).get(
                    "sufficiency_decision"),
                "allows_synthesis":
                    rep.final_recommendation.get("allows_synthesis", False),
                "generated_at": rep.generated_at.isoformat(),
                "event_count": len(cached.events),
            })
        return summaries

    def __len__(self) -> int:
        return len(self._items)


__all__ = ["CachedRun", "RunCache"]
