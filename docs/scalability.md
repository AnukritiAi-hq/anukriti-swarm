# Scalability Considerations

> Parallelism, distribution, and population-specialized reasoning strategies for Anukriti Swarm.

---

## Scaling Dimensions

```
┌─────────────────────────────────────────────────────────────┐
│                    SCALING AXES                              │
├─────────────────┬─────────────────┬─────────────────────────┤
│  HORIZONTAL     │  VERTICAL       │  DOMAIN                 │
│  (more agents)  │  (bigger agents)│  (specialized agents)   │
├─────────────────┼─────────────────┼─────────────────────────┤
│  Chromosome     │  Larger context │  Population-specific    │
│  parallelism    │  windows        │  reasoning models       │
│                 │                 │                         │
│  Multi-sample   │  Faster LLM     │  Gene-family            │
│  batch          │  inference      │  specialists            │
└─────────────────┴─────────────────┴─────────────────────────┘
```

---

## 1. Chromosome-Level Parallelism

The most natural parallelism axis. Each chromosome's variants are independent and can be analyzed concurrently.

### Execution Model

```
VCF Input ──partition──▶ [chr1, chr2, ..., chr22, chrX, chrY, chrMT]
                                    │
                         ┌──────────┼──────────┐
                         ▼          ▼          ▼
                    Chr1 Agent  Chr2 Agent  ChrN Agent   (up to 25 parallel)
                         │          │          │
                         └──────────┼──────────┘
                                    ▼
                              Merge Results
```

### Performance Characteristics

| Scenario | Sequential | Parallel (25 agents) | Speedup |
|----------|-----------|---------------------|---------|
| Full genome (4.2M variants) | ~120s | ~8s | 15x |
| Pharmacogene panel (847 variants) | ~5s | ~2s | 2.5x |
| Single gene query | ~1s | ~1s | 1x |

### Implementation Notes

- Partition VCF by chromosome before dispatch
- Each chromosome agent is stateless — no shared mutable state
- Results merge is a simple concatenation (no ordering dependency)
- Failed chromosome agents don't block others

---

## 2. Distributed Execution

### Single-Node (Development)

```
┌─────────────────────────────────────┐
│  Single Process                     │
│  ┌───────────┐  ┌───────────────┐  │
│  │Orchestrator│  │ Agent Pool    │  │
│  │           │  │ (async tasks) │  │
│  └───────────┘  └───────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ In-Memory State + Redis      │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

### Multi-Node (Production)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Node 1      │     │  Node 2      │     │  Node 3      │
│  Orchestrator│     │  Chr Agents  │     │  Pharma +    │
│  + API       │     │  (1-12)      │     │  Population  │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            ▼
              ┌──────────────────────────┐
              │  Shared Infrastructure   │
              │  Redis · MongoDB · Qdrant│
              └──────────────────────────┘
```

### Distribution Strategy

| Component | Distribution Model |
|-----------|-------------------|
| Orchestrator | Single leader (HA with failover) |
| Chromosome agents | Stateless workers, any node |
| Population agents | Pinned to nodes with population data |
| Retrieval agents | Co-located with vector DB |
| Memory layer | Centralized (Redis cluster, MongoDB replica set) |

---

## 3. Population-Specialized Reasoning

### Population Agent Fleet

Each major population group gets a dedicated agent with:
- Pre-loaded frequency data for that population
- Population-specific pharmacogenomic knowledge
- Tuned prompts for ethnopharmacogenomic reasoning

```
┌─────────────────────────────────────────────────────┐
│              POPULATION AGENT FLEET                  │
├──────────┬──────────┬──────────┬──────────┬─────────┤
│  SAS     │  EAS     │  AFR     │  EUR     │  AMR    │
│  (South  │  (East   │  (African│  (European│ (Admixed│
│   Asian) │   Asian) │         )│          )│  Amer.) │
└──────────┴──────────┴──────────┴──────────┴─────────┘
```

### Specialization Benefits

| Benefit | Mechanism |
|---------|-----------|
| Faster lookups | Pre-indexed population-specific frequency tables |
| Better context | Population-tuned prompts with relevant examples |
| Reduced noise | Only relevant population data loaded in context |
| Accuracy | Population-specific allele frequency thresholds |

---

## 4. Batch Processing

For multi-sample analysis (cohort studies):

```
Samples [S1, S2, ..., Sn]
         │
         ▼
┌─────────────────────────────┐
│  Batch Orchestrator         │
│  • Shared reference data    │
│  • Per-sample DAGs          │
│  • Cross-sample comparison  │
└─────────────────────────────┘
```

| Batch Size | Strategy |
|-----------|----------|
| 1–10 | Sequential DAGs, shared memory |
| 10–100 | Parallel DAGs, shared reference cache |
| 100+ | Distributed workers, partitioned by chromosome |

---

## 5. Resource Scaling Targets

| Load Level | Concurrent Queries | Infrastructure |
|-----------|-------------------|----------------|
| Dev | 1 | Single process, local DBs |
| Research | 5–10 | Single node, external DBs |
| Production | 50+ | Multi-node, clustered DBs |

### Bottleneck Analysis

| Component | Bottleneck | Mitigation |
|-----------|-----------|------------|
| LLM calls | Rate limits, latency | Request queuing, caching, batch |
| Vector search | Memory for large indices | Qdrant sharding |
| MongoDB | Write throughput (audit) | Batched writes, capped collections |
| VCF parsing | CPU for large files | Stream parsing, chromosome partitioning |
