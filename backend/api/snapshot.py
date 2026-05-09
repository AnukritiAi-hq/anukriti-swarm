"""Snapshot + replay + recent-runs endpoints.

Phase 3, commit 9 of the Unified Orchestration + Visualization brief.

Three read-only endpoints over ``RUN_CACHE``:

    GET /api/snapshot/{correlation_id}
        Returns just the UnifiedExecutionReport.to_dict() for the
        run. 404 if not cached. Frontend uses this when rendering
        a shared-link view (replay after a runtime restart isn't
        supported — the cache is per-worker).

    GET /api/replay/{correlation_id}
        Returns the full bundle (report + events + event_count).
        Same shape as /api/run's response, so client code can
        reuse its renderer. Used by the frontend's 'replay' button
        to re-animate a completed run without re-executing the
        lifecycle.

    GET /api/recent?limit=20
        Compact summaries of the N most-recent runs (correlation_id,
        scope keys, decision, allows_synthesis, generated_at,
        event_count). Drives the recent-runs UI panel.

The cache is in-memory and per-worker (see backend/cache.py). In a
single-worker dev setup (the default) this is fine; multi-worker
production would require MCP-backed replay which is a separate
follow-up.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.app import RUN_CACHE


router = APIRouter(prefix="/api", tags=["history"])


@router.get("/snapshot/{correlation_id}")
def snapshot(correlation_id: str) -> dict[str, Any]:
    """Return the UnifiedExecutionReport for a cached run."""

    cached = RUN_CACHE.get(correlation_id)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail=f"no cached run for correlation_id={correlation_id!r}",
        )
    return {"report": cached.report.to_dict()}


@router.get("/replay/{correlation_id}")
def replay(correlation_id: str) -> dict[str, Any]:
    """Return the full (report + events) bundle for a cached run."""

    cached = RUN_CACHE.get(correlation_id)
    if cached is None:
        raise HTTPException(
            status_code=404,
            detail=f"no cached run for correlation_id={correlation_id!r}",
        )
    return {
        "report": cached.report.to_dict(),
        "events": [e.to_dict() for e in cached.events],
        "event_count": len(cached.events),
    }


@router.get("/recent")
def recent(
    limit: int = Query(20, ge=1, le=64, description="Max runs to return"),
) -> dict[str, Any]:
    """Return compact summaries of the N most-recent cached runs.

    Summary shape matches RunCache.list_recent output — a stable
    JSON schema the frontend's recent-runs panel binds to.
    """

    summaries = RUN_CACHE.list_recent(limit=limit)
    return {"runs": summaries, "count": len(summaries)}


__all__ = ["router"]
