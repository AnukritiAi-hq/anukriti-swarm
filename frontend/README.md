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
- **Cinematic pacing** — a 320ms per-stage delay is applied client-side so the orchestration lifecycle is visible even though the backend completes in ~5ms. Labeled as presentation pacing in the UI, not disguised as computation time. Toggle off for raw-speed engineer mode.
- **Origin labelling** — green borders (deterministic/established) vs purple (generative/narrative)
- **Closed enums everywhere** — decision / verdict / uncertainty / bias use fixed colour maps, not dynamic styling
- **D3 only for graph views** — vendored single-file copy; no build step, no npm install
- **Real data, no mocks** — phenotype inference, population frequencies, and CPIC recommendations all come from the repository's real deterministic sources (see below)

## Real-data guarantees

Every value rendered by the UI can be traced back to a deterministic source:

| Signal | Source |
|---|---|
| Phenotype | `rules/phenotype_rules.py:infer_phenotype` (CPIC activity-score) + `agents/pharmacogene/hla_b.py:HLABAgent` (binary carrier status) |
| Population allele frequency | `knowledge_graph.PopulationGraphIndexer.alleles_for(pop)` from HIGHER_FREQUENCY_IN edges |
| Recommendation text | `guidelines/cpic.py:lookup_recommendation` — verbatim CPIC guideline text + strength + PMID |
| Evidence citations | `retrieval/evidence/documents.py` seeded CPIC/PharmGKB/PubMed documents |
| KG paths | `knowledge_graph.MultiHopReasoner` bounded BFS (≤4 hops) over the 37-node / 34-edge seed graph |
| Sufficiency decision | `core/evidence_sufficiency/sufficiency/decision_engine.py` — 12-rule closed table |
| Verdict | `core/evidence_sufficiency/verifier/set_level.py` — 10-rule closed table |
| Uncertainty tier | `core/evidence_sufficiency/uncertainty/engine.py` — 9-rule closed table |
| Bias findings | `core/evidence_sufficiency/uncertainty/bias_detector.py` — 3-class detector with numeric thresholds |

The only "mock" is the offline-fallback render that fires when the backend is unreachable on page load; it's labeled as such via the yellow `● offline` badge.

## Future (out of scope for session #7)

- Shared-link views via `/api/snapshot/{id}`
- Replay animations via `/api/replay/{id}`
- Comparative side-by-side view running the flagship trio simultaneously (session #7 phase 6)
- PDF report export
- Authenticated multi-user sessions
