# 🧬 Anukriti Swarm

**Distributed multi-agent genomic intelligence infrastructure for population-aware pharmacogenomic reasoning.**

> ⚠️ **Research Only** — This system is designed for academic and research exploration. It is not intended for clinical decision-making or diagnostic use.

---

## Vision

Anukriti Swarm is a multi-agent architecture that decomposes complex pharmacogenomic reasoning into specialized, composable intelligence units. Each agent operates on a defined genomic domain — from chromosome-level variant analysis to population-level allele frequency reasoning — coordinated by a central orchestrator that enforces deterministic reproducibility.

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│              Orchestrator Agent                  │
│         (routing, validation, consensus)        │
├─────────────┬───────────────┬───────────────────┤
│ Population  │  Chromosome   │   Pharmacogenomic │
│ Agents      │  Agents       │   Specialist      │
│ (ancestry,  │  (variant     │   (drug-gene      │
│  frequency) │   calling)    │    interaction)   │
└─────────────┴───────────────┴───────────────────┘
         │              │               │
         ▼              ▼               ▼
┌─────────────────────────────────────────────────┐
│           Shared Memory Layer                   │
│     (vector store, state, audit trail)          │
└─────────────────────────────────────────────────┘
```

## Key Principles

- **Deterministic + Generative Separation** — Factual lookups (allele frequencies, known interactions) are deterministic; reasoning and hypothesis generation use LLMs with full traceability.
- **Population-Aware** — Every inference is contextualized by population-specific genomic data.
- **Auditable** — All agent decisions are logged with provenance for reproducibility.
- **Modular** — Agents can be added, removed, or replaced without system-wide changes.

## Project Structure

```
anukriti-swarm/
├── agents/          # Multi-agent swarm modules
├── backend/         # API and orchestration services
├── frontend/        # Visualization and dashboard UI
├── workflows/       # Pipeline definitions and DAGs
├── memory/          # Shared memory and state stores
├── datasets/        # Reference genomic datasets
├── architecture/    # System design documents and diagrams
├── docs/            # Project documentation
├── demos/           # Demonstration notebooks and scripts
├── experiments/     # Research experiments and benchmarks
├── scripts/         # Utility and automation scripts
└── tests/           # Test suites
```

## Quick Start

```bash
# Clone
git clone https://github.com/your-org/anukriti-swarm.git
cd anukriti-swarm

# Setup environment
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Verify setup
make lint
make test
```

## Development

| Command        | Description              |
|----------------|--------------------------|
| `make install` | Install dependencies     |
| `make lint`    | Run ruff + mypy          |
| `make format`  | Auto-format code         |
| `make test`    | Run pytest               |
| `make clean`   | Remove build artifacts   |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache 2.0 — See [LICENSE](LICENSE).

---

*Built for research. Not for clinical use.*
