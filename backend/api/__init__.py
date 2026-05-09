"""REST API routers for the Anukriti Swarm backend.

Phase 3 of the Unified Orchestration + Visualization brief.

Each submodule registers a router on the main FastAPI application.
Every endpoint returns JSON; all payloads are ``.to_dict()`` output
from frozen dataclasses so the shape is auditable.

Endpoints (populated through phase 3):

    health.py       GET /api/health         liveness probe (commit 7)
                    GET /api/scenarios      canonical scenario list
    run.py          POST /api/run           synchronous unified execution
                    (commit 8)
    snapshot.py     GET /api/snapshot/{id}  cached run retrieval
                    GET /api/replay/{id}    full event + report bundle
                    GET /api/recent         recent-run summary list
                    (commit 9)
"""

from __future__ import annotations

__all__: list[str] = []
