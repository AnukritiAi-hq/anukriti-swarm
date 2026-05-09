# Anukriti Swarm — Frontend

Live orchestration interface for distributed genomic intelligence.

## Quick Start

### Live mode (recommended)

```bash
# terminal 1 — backend
cd ..
source venv/bin/activate
uvicorn backend.app:app --host 127.0.0.1 --port 8000

# terminal 2 — frontend
cd frontend
python -m http.server 3000

# browser
open http://localhost:3000/pages/index.html
```

The frontend auto-detects the backend on page load via `/api/health`.
When live, the header shows a green `● live` badge and:

- Selecting a canonical scenario populates the input form
- Clicking **Activate Swarm** opens a WebSocket to `/ws/run`, streams
  orchestration events as the lifecycle runs, and renders each
  panel progressively
- A terminal `report` frame finalises the aggregated view

### Offline mode (no backend)

```bash
cd frontend
python -m http.server 3000
open http://localhost:3000/pages/index.html
```

The frontend detects the backend is unreachable, shows a yellow
`● offline` badge, and falls back to a static mock result so the
page is still demoable without a running backend.

## Architecture

```
frontend/
├── pages/index.html          Single-page interface; 12 sections
├── components/styles.css     Dark scientific theme; D3 + chip + bar styles
├── visualization/swarm-viz.js Live backend client + renderers (~900 lines)
└── vendor/d3.v7.min.js       D3 v7.9.0 (MIT) for the graph explorer
```

## Backend surface consumed

| Route | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Liveness probe (boot-time detection) |
| `/api/scenarios` | GET | Populates the canonical scenario picker |
| `/api/run` | POST | Sync execution (fetch fallback) |
| `/api/snapshot/{id}` | GET | (reserved for shared-link views) |
| `/api/replay/{id}` | GET | (reserved for replay animations) |
| `/ws/run` | WS | Live event stream — primary execution channel |

See `architecture/backend-api.md` (session #7 phase 7) for the
full endpoint reference and WebSocket protocol.

## Sections (top to bottom)

| Section | Data source | Purpose |
|---|---|---|
| Query Input | form | Select scenario or custom scope |
| Swarm Activity | RuntimeEvent stream | Line-by-line live trace |
| Evidence Sufficiency | `evidence_sufficiency` | Decision / verdict / uncertainty gate |
| Population Intelligence | `graph_traversal` + `bias_findings` | Ancestry-weighted allele freq + bias signals |
| Knowledge Graph Explorer | `graph_traversal` paths | D3 force-directed KG traversal |
| Deterministic Governance | `deterministic_rules` + `provenance_chain` | Rule families + provenance records |
| Orchestration | `activated_agents` | Agent topology |
| Population Context | report | Target population summary |
| Pharmacogene Reasoning | report | Gene + genotype + decision + verdict |
| Evidence Retrieval | report | Citations + grounding % |
| Verification & Safety | report | Gate + verdict + rule count |
| Confidence Propagation | report | Coverage / verdict / uncertainty bars |
| Analysis Report | `final_recommendation` | Narrative OR abstention banner |
| Provenance & Auditability | report | Correlation id + duration + rule trail |

## Design principles

- **Live-first, offline-fallback** — the primary UX assumes a backend; the mock is a safety net, not the default
- **Dark scientific theme** — clinical precision, monospace data, subdued palette
- **Progressive reveal** — sections appear as the lifecycle emits events
- **Origin labelling** — green borders (deterministic/established) vs purple (generative/narrative)
- **Closed enums everywhere** — decision / verdict / uncertainty / bias use fixed colour maps, not dynamic styling
- **D3 only for graph views** — vendored single-file copy; no build step, no npm install

## Future (out of scope for session #7)

- Shared-link views via `/api/snapshot/{id}`
- Replay animations via `/api/replay/{id}`
- Comparative side-by-side view running the flagship trio simultaneously (session #7 phase 6)
- PDF report export
- Authenticated multi-user sessions
