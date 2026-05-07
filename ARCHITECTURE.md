# Architecture

> ⚠️ **Research Only** — This architecture is designed for academic exploration of multi-agent pharmacogenomic reasoning. Not for clinical use.

---

## System Philosophy

Anukriti Swarm separates genomic intelligence into two distinct execution modes:

| Mode | Purpose | Implementation |
|------|---------|----------------|
| **Deterministic** | Factual lookups — allele frequencies, known drug-gene interactions, variant annotations | Rule engines, database queries, validated datasets |
| **Generative** | Hypothesis generation, novel interaction reasoning, population-level inference | LLM agents with full provenance logging |

This separation ensures that established genomic facts are never hallucinated, while exploratory reasoning remains traceable and auditable.

---

## Agent Taxonomy

### Orchestrator Agent

The central coordinator responsible for:
- Routing queries to appropriate specialist agents
- Enforcing deterministic-first resolution (facts before inference)
- Aggregating multi-agent responses into consensus outputs
- Maintaining audit trails for all decisions

### Population Agents

Specialized in population-level genomic reasoning:
- Ancestry-specific allele frequency lookups
- Population stratification analysis
- Cross-population variant comparison
- Ethnopharmacogenomic contextualization

### Chromosome Agents

Domain-specific agents for genomic regions:
- Variant calling and annotation
- Gene-level structural analysis
- Haplotype block identification
- Linkage disequilibrium reasoning

### Pharmacogenomic Specialist

Focused on drug-gene interaction intelligence:
- Known interaction lookup (deterministic)
- Novel interaction hypothesis (generative)
- Dosage adjustment reasoning
- Adverse reaction prediction

---

## Data Flow

```
┌──────────┐     ┌──────────────┐     ┌─────────────────┐
│  Query   │────▶│ Orchestrator │────▶│ Agent Selection  │
└──────────┘     └──────────────┘     └─────────────────┘
                                              │
                        ┌─────────────────────┼─────────────────────┐
                        ▼                     ▼                     ▼
                 ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
                 │ Population  │     │ Chromosome   │     │ Pharmaco-    │
                 │ Agent       │     │ Agent        │     │ genomic      │
                 └──────┬──────┘     └──────┬───────┘     └──────┬───────┘
                        │                   │                     │
                        ▼                   ▼                     ▼
                 ┌─────────────────────────────────────────────────────┐
                 │              Shared Memory Layer                    │
                 │  (vector store, state graph, audit log)            │
                 └─────────────────────────────────────────────────────┘
                                        │
                                        ▼
                 ┌─────────────────────────────────────────────────────┐
                 │              Consensus + Response                   │
                 └─────────────────────────────────────────────────────┘
```

---

## Shared Memory Layer

All agents read from and write to a shared memory layer that provides:

- **Vector Store** — Semantic retrieval of genomic knowledge, research papers, and prior reasoning chains
- **State Graph** — Current query context, intermediate results, and agent coordination state
- **Audit Trail** — Immutable log of every agent decision with timestamps and provenance

---

## Design Constraints

1. **No clinical decisions** — System outputs are research artifacts, not medical advice
2. **Deterministic first** — Always resolve via known data before invoking generative reasoning
3. **Population context required** — No inference without explicit population anchoring
4. **Full traceability** — Every output links back to source data and reasoning chain
5. **Agent isolation** — Agents share state through memory layer only, never direct coupling

---

## Technology Stack (Planned)

| Layer | Technology |
|-------|-----------|
| Orchestration | LangChain / LangGraph |
| LLM Backend | OpenAI GPT-4, Anthropic Claude |
| Vector Store | Qdrant |
| API | FastAPI |
| Frontend | Next.js |
| Data | Pandas, NumPy |
| Testing | Pytest |

---

## Next Steps

See [ROADMAP.md](ROADMAP.md) for implementation phases.
