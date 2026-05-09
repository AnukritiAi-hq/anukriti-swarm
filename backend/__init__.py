"""Anukriti Swarm — FastAPI backend.

Phase 3 of the Unified Orchestration + Visualization brief.

This package exposes the ``SwarmRuntime`` over HTTP + WebSocket so
the static frontend (phase 4) can drive live pharmacogenomic runs
and stream orchestration events as they happen.

Scope firewall (read before extending)
--------------------------------------

The backend is **not**:

    • an authentication / user-account service
    • a database layer — in-memory caches only; MCP already
      persists what needs persisting
    • a multi-tenant SaaS surface
    • a chatbot / conversation service
    • a generic healthcare API

It is:

    • a thin JSON + WebSocket facade over SwarmRuntime
    • one runtime per request; concurrency is handled by
      FastAPI + uvicorn workers, not by the runtime
    • JSON-safe by construction (every response is
      UnifiedExecutionReport.to_dict or RuntimeEvent.to_dict)

Subpackages
-----------

    api/     REST endpoints (POST /api/run, snapshot, replay,
             health, scenarios). Synchronous request/response.
    ws/      WebSocket endpoint (WS /ws/run). Streams
             RuntimeEvents as the lifecycle progresses.
    app.py   FastAPI application factory + lifespan hooks.
    cache.py in-memory correlation-id keyed report cache.

Launch:
    uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

__all__: list[str] = []
