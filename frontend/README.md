# Anukriti Swarm — Frontend

Research-grade interface for distributed genomic intelligence.

## Quick Start

```bash
cd frontend
python -m http.server 3000
# Open http://localhost:3000/pages/index.html
```

## Architecture

```
frontend/
├── pages/index.html          # Single-page research interface
├── components/styles.css     # Scientific dark theme
└── visualization/swarm-viz.js # Agent orchestration visualization
```

## Design Principles

- **Zero dependencies** — pure HTML/CSS/JS, no build step
- **Dark scientific theme** — clinical precision, monospace data
- **Progressive reveal** — sections appear as pipeline executes
- **Origin labeling** — green borders (established) vs purple (narrative)
- **Confidence visualization** — animated bars with color coding

## Sections

| Section | Shows |
|---------|-------|
| Query Input | Gene, drug, ancestry, diplotype selection |
| Swarm Activity | Real-time execution trace |
| Orchestration | Agent topology graph |
| Population | Frequency, rarity, confidence metrics |
| Pharmacogene | Phenotype, risk, activity score |
| Evidence | Citations, grounding score |
| Verification | Verdict, checks, escalation |
| Confidence | Stage-by-stage propagation bars |
| Narrative | 3-audience report (patient/researcher/audit) |
| Provenance | Full audit trail |

## Future

- WebSocket connection to Python backend
- Real-time streaming of pipeline execution
- Interactive agent graph (D3.js)
- PDF report export
