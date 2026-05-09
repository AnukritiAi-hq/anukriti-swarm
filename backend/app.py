"""FastAPI application factory for the Anukriti Swarm backend.

Phase 3, commit 7 of the Unified Orchestration + Visualization brief.

Provides the ``app`` ASGI object uvicorn runs plus a ``build_app()``
factory tests can call to get an isolated instance.

The app wires:
  - CORS middleware (permissive for localhost frontend at :3000)
  - /api/health  — liveness check
  - /api/scenarios — the three canonical brief-named scenarios
  - /api/run (commit 8)
  - /api/snapshot/{correlation_id} + /api/replay (commit 9)
  - /ws/run (commit 10)

Module state (per uvicorn worker):
  RUN_CACHE      bounded in-memory cache of CachedRun entries
                 (keyed by correlation_id)
  SHARED_RUNTIME a single SwarmRuntime whose shared components
                 (KG, indexer, retrievers, checkpoint) are built
                 once per worker and reused across requests

Scope firewall
--------------
No auth, no database, no multi-tenant surface. The CORS setting is
permissive only for the localhost development frontend; a real
deployment tightens this.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.cache import RunCache
from core.models.population import SuperPopulation
from core.runtime import SwarmRuntime


# ---------------------------------------------------------------------------
# Worker-scope singletons
# ---------------------------------------------------------------------------


RUN_CACHE = RunCache(max_entries=64)
SHARED_RUNTIME: SwarmRuntime | None = None  # set in build_app


# ---------------------------------------------------------------------------
# Canonical scenarios exposed via /api/scenarios
# ---------------------------------------------------------------------------


CANONICAL_SCENARIOS = [
    {
        "id": "cyp2c19_clopidogrel_sas",
        "title": "Clopidogrel + CYP2C19 + South Asian",
        "subtitle": "36% SAS carry CYP2C19*2 (loss-of-function)",
        "drug": "clopidogrel", "gene": "CYP2C19",
        "population": SuperPopulation.SAS.value, "genotype": "*2/*2",
    },
    {
        "id": "hlab_cbz_eas",
        "title": "Carbamazepine + HLA-B*15:02 + East Asian",
        "subtitle": "HLA-B*15:02 carriers contraindicated for CBZ",
        "drug": "carbamazepine", "gene": "HLA-B",
        "population": SuperPopulation.EAS.value, "genotype": "*15:02/positive",
    },
    {
        "id": "cyp2d6_codeine_afr",
        "title": "Codeine + CYP2D6 + African ancestry",
        "subtitle": "CYP2D6*4 PM in AFR; seed lacks AFR-specific evidence",
        "drug": "codeine", "gene": "CYP2D6",
        "population": SuperPopulation.AFR.value, "genotype": "*4/*4",
    },
]


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def build_app() -> FastAPI:
    """Build + wire the FastAPI app. Importers can rely on global ``app``."""

    global SHARED_RUNTIME
    if SHARED_RUNTIME is None:
        # Building the runtime triggers the lazy KG/indexer build on
        # first request, not at import time.
        SHARED_RUNTIME = SwarmRuntime()

    application = FastAPI(
        title="Anukriti Swarm",
        description="Unified genomic intelligence orchestration API.",
        version="0.1.0",
    )

    # CORS — permissive for the localhost demo frontend.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers — registered via add_* modules below.
    from backend.api import health as _health
    from backend.api import run as _run
    from backend.api import snapshot as _snapshot
    from backend.ws import run as _ws_run
    application.include_router(_health.router)
    application.include_router(_run.router)
    application.include_router(_snapshot.router)
    application.include_router(_ws_run.router)

    return application


app = build_app()


__all__ = [
    "app",
    "build_app",
    "CANONICAL_SCENARIOS",
    "RUN_CACHE",
    "SHARED_RUNTIME",
]
