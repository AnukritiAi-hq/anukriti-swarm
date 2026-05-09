"""Health + scenarios endpoints.

Phase 3, commit 7 of the Unified Orchestration + Visualization brief.

Two routes:

    GET /api/health     liveness probe; returns a small JSON body
                        the frontend can poll on page load to
                        detect whether the backend is running
                        (the frontend falls back to a static mock
                        when the backend is unreachable).

    GET /api/scenarios  returns the three canonical brief-named
                        scenarios (clopidogrel/CYP2C19/SAS,
                        CBZ/HLA-B/EAS, codeine/CYP2D6/AFR). The
                        frontend drives its selector from this
                        response rather than hard-coding scenarios.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.app import CANONICAL_SCENARIOS, RUN_CACHE


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    """Liveness probe — returns basic system + cache state."""

    return {
        "status": "ok",
        "service": "anukriti-swarm",
        "version": "0.1.0",
        "cache_size": len(RUN_CACHE),
    }


@router.get("/scenarios")
def scenarios() -> dict[str, object]:
    """Return the canonical brief-named scenario list."""

    return {
        "scenarios": list(CANONICAL_SCENARIOS),
        "count": len(CANONICAL_SCENARIOS),
    }


__all__ = ["router"]
