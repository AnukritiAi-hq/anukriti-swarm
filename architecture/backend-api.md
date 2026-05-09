# Backend API — Anukriti Swarm

**Status:** production — FastAPI + WebSocket backend shipped (session #7 phase 3).
**Transport:** HTTP/1.1 + WebSocket over localhost; 6 REST routes + 1 WebSocket route.

## Scope firewall

The backend is **not**:

- an authentication / authorization service
- a persistence layer (caches are per-worker in-memory; MCP persists what needs persisting)
- a multi-tenant SaaS surface
- a chatbot or conversation service
- a generic healthcare API

It IS a thin JSON + WebSocket façade over `SwarmRuntime` with one runtime per request; concurrency is handled by FastAPI + uvicorn workers.

## Endpoint surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness probe |
| GET | `/api/scenarios` | 3 canonical scenarios for the UI picker |
| POST | `/api/run` | Synchronous unified execution |
| GET | `/api/snapshot/{id}` | Cached report-only retrieval |
| GET | `/api/replay/{id}` | Cached report + events |
| GET | `/api/recent` | MRU summaries |
| WS | `/ws/run` | Live event-streaming orchestration |

## Launch

```bash
source venv/bin/activate
uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

One uvicorn worker by default. `backend/app.py` exposes `app` (a `FastAPI` instance) and `build_app()` (for tests wanting isolated instances).

## CORS

Permissive for the localhost frontend at `:3000`. Production deployment tightens this.

```python
allow_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
```

## REST endpoints

### `GET /api/health`

Liveness probe. The frontend polls this on `DOMContentLoaded` to decide between live mode and offline-mock mode.

**Response** (200):
```json
{
  "status": "ok",
  "service": "anukriti-swarm",
  "version": "0.1.0",
  "cache_size": 0
}
```

### `GET /api/scenarios`

Returns the three canonical brief-named scenarios. The frontend populates the scenario picker from this response rather than hard-coding scenarios.

**Response** (200):
```json
{
  "scenarios": [
    {
      "id": "cyp2c19_clopidogrel_sas",
      "title": "Clopidogrel + CYP2C19 + South Asian",
      "subtitle": "36% SAS carry CYP2C19*2 (loss-of-function)",
      "drug": "clopidogrel", "gene": "CYP2C19",
      "population": "SAS", "genotype": "*2/*2"
    },
    {
      "id": "hlab_cbz_eas",
      "title": "Carbamazepine + HLA-B*15:02 + East Asian",
      "subtitle": "HLA-B*15:02 carriers contraindicated for CBZ",
      "drug": "carbamazepine", "gene": "HLA-B",
      "population": "EAS", "genotype": "*15:02/positive"
    },
    {
      "id": "cyp2d6_codeine_afr",
      "title": "Codeine + CYP2D6 + African ancestry",
      "subtitle": "CYP2D6*4 PM in AFR; seed lacks AFR-specific evidence",
      "drug": "codeine", "gene": "CYP2D6",
      "population": "AFR", "genotype": "*4/*4"
    }
  ],
  "count": 3
}
```

### `POST /api/run`

Synchronous unified-execution endpoint. Runs the full `SwarmRuntime` lifecycle, caches the result in `RUN_CACHE`, returns the report + event stream in the same JSON response.

Clients that don't need live streaming (CI, replay, batch, tests) use this path. The WebSocket route is preferred for live UIs.

**Request body** (pydantic `RunRequest`):
```json
{
  "drug": "clopidogrel",
  "gene": "CYP2C19",
  "population": "SAS",
  "genotype": "*2/*2",
  "question": "",
  "correlation_id": ""
}
```

Fields:
- `drug` — required, str, `min_length=1`, case-insensitive
- `gene` — required, str, `min_length=1`, case-insensitive
- `population` — required, `SuperPopulation` 3-letter code (`AFR` / `AMR` / `EAS` / `EUR` / `SAS`)
- `genotype` — optional, defaults to `"unknown"`
- `question` — optional free-form string
- `correlation_id` — optional; runtime generates `unified_<hex>` if empty

**Response** (200):
```json
{
  "report": { /* UnifiedExecutionReport.to_dict() — 18 top-level fields */ },
  "events": [ /* list of RuntimeEvent.to_dict() in emission order */ ],
  "event_count": 14
}
```

**Status codes**:
- `200` — successful lifecycle (including safe-abstention paths; abstention is a business outcome, not an error)
- `400` — scope firewall rejection (`UnifiedExecutionContext.new` ValueError)
- `422` — pydantic schema rejection (empty required fields)

**Behaviour**:
- Every invocation uses a fresh `SwarmRuntime` with a fresh `InMemoryEventStream` — event streams don't interleave across concurrent requests
- Result persisted into `RUN_CACHE` for subsequent `/api/snapshot` + `/api/replay`
- Case-insensitive drug/gene: `'CLOPIDOGREL'` / `'cyp2c19'` / `'sas'` all normalise via `UnifiedExecutionContext.new`

### `GET /api/snapshot/{correlation_id}`

Returns just the `UnifiedExecutionReport` for a cached run. Used for shared-link views where only the final report matters.

**Response** (200):
```json
{ "report": { /* UnifiedExecutionReport.to_dict() */ } }
```

**Errors**:
- `404` — no cached run for the id (`{"detail": "no cached run for correlation_id=..."}`)

### `GET /api/replay/{correlation_id}`

Returns the full bundle — same shape as `POST /api/run`'s response — so the frontend's event-rendering code can be reused verbatim for replay animations without re-executing the lifecycle.

**Response** (200):
```json
{
  "report": { /* UnifiedExecutionReport.to_dict() */ },
  "events": [ /* list */ ],
  "event_count": 14
}
```

For WebSocket-originated runs, `events` is empty (events were streamed live; only the report is cached).

### `GET /api/recent?limit=20`

Returns compact summaries of the N most-recent cached runs. Drives the recent-runs UI panel.

**Query params**:
- `limit` — int, default 20, min 1, max 64

**Response** (200):
```json
{
  "runs": [
    {
      "correlation_id": "unified_abc123...",
      "drug": "clopidogrel",
      "gene": "CYP2C19",
      "population": "SAS",
      "genotype": "*2/*2",
      "decision": "sufficient",
      "allows_synthesis": true,
      "generated_at": "2026-05-09T17:30:00+00:00",
      "event_count": 14
    }
  ],
  "count": 1
}
```

Order is MRU — most-recently-accessed first. `/api/snapshot` and `/api/replay` both move-to-MRU on access, so this reflects most-recently-touched, not most-recently-created.

## WebSocket endpoint

### `WS /ws/run`

Live orchestration event stream. The primary execution channel for live UIs.

**Contract**:
1. Client connects.
2. Client sends one JSON message with the scope tuple (identical shape to `/api/run`'s request body).
3. Server validates via `UnifiedExecutionContext.new`. On validation failure, server sends `{type:"error", code:"bad_scope", detail:"..."}` and closes.
4. Server instantiates `SwarmRuntime` with an `AsyncQueueEventStream` and runs the lifecycle on a worker thread (`asyncio.to_thread`).
5. Server forwards each `RuntimeEvent` as a JSON message as it's emitted:
   ```json
   {
     "type": "event",
     "event_id": "a1b2c3d4e5f6...",
     "kind": "run_started",
     "correlation_id": "unified_abc123...",
     "timestamp": "2026-05-09T17:30:00+00:00",
     "payload": { /* kind-specific primitive-only dict */ }
   }
   ```
6. Server sends a terminal `{type:"report", report: {...}, event_count: N}` message with the full `UnifiedExecutionReport`.
7. Server closes the connection.

**Error channels** (all typed):
- `{type:"error", code:"bad_json", detail:"..."}` — malformed initial payload
- `{type:"error", code:"bad_scope", detail:"..."}` — scope validation failure
- `{type:"error", code:"server_error", detail:"..."}` — uncaught server exception
- Connection close with code `1011` — fatal server error

**Why a worker thread?** The `SwarmRuntime` is synchronous (~5 ms per scenario). Running it directly on the event loop blocks other connections during that window. The thread+queue pattern keeps the event loop responsive and delivers per-event latency so frontend animations feel live.

**Cache behaviour for WS-originated runs**: `RUN_CACHE` stores the report only (events were streamed live to the client). `/api/replay` on a WS-originated `correlation_id` returns the report with `event_count=0`; clients that need event playback use `/api/run` (sync path) instead.

## Event kinds streamed over `/ws/run`

12 closed kinds (see `architecture/unified-runtime.md` for the full table):

| Kind | Payload shape (primitive-only) |
|---|---|
| `run_started` | `{drug, gene, population, genotype}` |
| `agent_activated` | `{agent}` |
| `retrieval_complete` | `{citations: [], total_retrieved, strategy}` |
| `graph_traversal` | `{start_id, goal_id, path_count, paths: []}` |
| `sufficiency_decision` | `{decision, rationale, coverage_ratio, missing_facets: [], uncertain_facets: []}` |
| `verification_checkpoint` | `{verdict, rule_id, rationale, pathway_complete, pathway_count}` |
| `uncertainty_transition` | `{score, action, rationale, bias_findings: []}` |
| `provenance_persisted` | `{record_count, records: []}` |
| `synthesis_emitted` | `{audiences: [], patient_excerpt}` |
| `safe_abstention` | `{blocking_reason, decision, verdict}` |
| `run_completed` | `{duration_ms, activated_agents: []}` |
| `run_failed` | `{error}` |

Extending is a code change; enum enforced at the type boundary.

## Event count per scenario

- **Sufficient run** (e.g. Clopidogrel + CYP2C19 + SAS): **14 events**
  `run_started` + 5× `agent_activated` + `retrieval_complete` + `graph_traversal` + `sufficiency_decision` + `verification_checkpoint` + `uncertainty_transition` + `provenance_persisted` + `synthesis_emitted` + `run_completed`

- **Abstention run** (e.g. Codeine + CYP2D6 + AFR): **13 events**
  Same as sufficient minus `agent_activated(narrative_agent)` and `synthesis_emitted`; plus `safe_abstention`.

## Cache

`backend/cache.py` — bounded LRU keyed by `correlation_id`.

- **Capacity**: 64 runs (configurable via `RunCache(max_entries=N)`)
- **LRU semantics**: `.put` / `.get` both move-to-MRU; oldest evicted on overflow
- **Per-worker**: each uvicorn worker has its own cache; no cross-worker sharing
- **In-memory only**: restart clears everything; MCP-backed replay requires an external store

`CachedRun` holds the `UnifiedExecutionReport` + tuple of `RuntimeEvent`s. WebSocket-originated runs store `events=()` since the client already received them live.

## Test client verification

FastAPI's `TestClient` supports both HTTP and WebSocket transports. The phase-3 smoke tests used it to verify:

- All 6 REST endpoints return expected shapes on happy paths
- WebSocket streams 14/13 events matching the runtime's emission order
- Bad scope over HTTP → 400; over WS → `{type:"error", code:"bad_scope"}`
- Malformed JSON over WS → `{type:"error", code:"bad_json"}`
- LRU eviction on cache overflow (not exercised at default capacity)
- Cross-request determinism

## Dependencies

Pinned in `requirements.txt`:

```
pydantic==2.7.1
fastapi==0.111.0
uvicorn==0.29.0
websockets==15.0.1
```

`websockets==15.0.1` pinned explicitly to satisfy `google-adk`'s constraint (`>=15.0.1`) without version drift. FastAPI + uvicorn were already pinned pre-session-7.

## Frontend client

The frontend (`frontend/visualization/swarm-viz.js`) consumes:

- `GET /api/health` on page load to choose live vs offline mode
- `GET /api/scenarios` to populate the scenario picker
- `WS /ws/run` as the primary execution channel (live event animation)
- `POST /api/run` as the fallback when WS fails (browser blocks WS, proxy strips upgrade, etc.)

When the backend is unreachable at boot, the frontend renders a static mock so the page stays demoable without a server. See `frontend/README.md` for setup.

## Performance

- Single `/api/run` latency: ~5-8 ms (runtime + serialization)
- WS per-event latency: dominated by browser paint
- WS connection overhead: first connection includes the KG + indexer build (~30 ms); subsequent connections reuse `SHARED_RUNTIME`'s components

## File map

```
backend/
  __init__.py                top-level scope firewall docstring
  app.py                     FastAPI factory + RUN_CACHE +
                             SHARED_RUNTIME + CORS + router wiring
  cache.py                   CachedRun + RunCache (bounded LRU)
  api/
    __init__.py
    health.py                /api/health + /api/scenarios
    run.py                   POST /api/run
    snapshot.py              /api/snapshot + /api/replay + /api/recent
  ws/
    __init__.py
    run.py                   WS /ws/run + AsyncQueueEventStream
```

## Continuation pointers

- **Shared-link views** — `/api/snapshot/{id}` already works; the frontend can add a URL-hash router to render a specific cached run
- **Replay animations** — `/api/replay/{id}` returns events; the frontend can re-animate a completed run without re-executing
- **Multi-worker cache** — back `RUN_CACHE` with MCP for cross-worker replay
- **Recent-runs panel** — the `/api/recent` endpoint is ready; a UI panel binding to it would live alongside the existing sections
- **Authentication** — out of scope for this session; a real deployment adds FastAPI security middleware

## Out of scope (do not build here)

- Authentication / user accounts
- Persistent database (use MCP)
- Multi-tenant session storage
- Server-side graph computation (the KG lives client-side in the runtime, server-side via `PharmacogenomicKnowledgeGraph` — no graph query language exposed)
- Rate limiting / quotas
- Multi-region deployment concerns
