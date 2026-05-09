"""Synchronous unified-execution endpoint.

Phase 3, commit 8 of the Unified Orchestration + Visualization brief.

Single endpoint:

    POST /api/run
    body: {drug, gene, population, genotype, question?, correlation_id?}
    response: UnifiedExecutionReport.to_dict()  +  events: list of
              RuntimeEvent.to_dict() in emission order

The endpoint runs the full SwarmRuntime lifecycle synchronously,
stores the result in RUN_CACHE, and returns the report + event
stream in the same JSON response. Clients that don't need live
streaming (CI / replay / unit tests / batch) use this path.

The WebSocket path (/ws/run, commit 10) is preferred for the live
frontend because events arrive as they're emitted. This endpoint
waits for completion.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app import RUN_CACHE
from backend.cache import CachedRun
from core.models.population import SuperPopulation
from core.runtime import (
    InMemoryEventStream,
    SwarmRuntime,
    UnifiedExecutionContext,
)


router = APIRouter(prefix="/api", tags=["execution"])


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    """Input for /api/run — mirrors UnifiedExecutionContext.new() scope."""

    drug: str = Field(..., min_length=1, description="Drug name (case-insensitive)")
    gene: str = Field(..., min_length=1, description="Gene symbol (case-insensitive)")
    population: str = Field(
        ..., min_length=1,
        description="SuperPopulation 3-letter code (AFR/AMR/EAS/EUR/SAS)",
    )
    genotype: str = Field("unknown", description="Diplotype like *2/*2")
    question: str = Field("", description="Optional free-form query text")
    correlation_id: str = Field(
        "", description="Optional caller-supplied id for MCP linkage",
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/run")
def run_unified(req: RunRequest) -> dict[str, Any]:
    """Execute the unified lifecycle and return the full report + event stream.

    Every invocation spins up a fresh ``SwarmRuntime`` with a fresh
    ``InMemoryEventStream``. Shared components in ``SHARED_RUNTIME``
    are pre-warmed for latency, but the per-request runtime is
    independent so concurrent requests don't step on each other's
    event streams.

    Returns (JSON):
        report: UnifiedExecutionReport.to_dict()
        events: list[RuntimeEvent.to_dict()]
        event_count: int
    """

    # Scope validation via the factory; malformed input -> 400.
    try:
        ctx = UnifiedExecutionContext.new(
            drug=req.drug,
            gene=req.gene,
            population=req.population,
            genotype=req.genotype,
            question=req.question,
            correlation_id=req.correlation_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Fresh runtime per request. Components are lazy-built on first
    # run() call; for a long-running server the cached SHARED_RUNTIME
    # in backend.app provides the warm-start path, but here we
    # prioritise isolation so events don't interleave across requests.
    runtime = SwarmRuntime(event_stream=InMemoryEventStream())
    report = runtime.run(ctx)

    # Persist into the cache for /api/snapshot + /api/replay.
    events = tuple(runtime.event_stream.events)
    RUN_CACHE.put(ctx.correlation_id, CachedRun(report=report, events=events))

    return {
        "report": report.to_dict(),
        "events": [e.to_dict() for e in events],
        "event_count": len(events),
    }


__all__ = ["router"]
