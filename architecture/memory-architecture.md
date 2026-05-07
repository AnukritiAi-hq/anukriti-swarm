# Memory Architecture

> 4-layer memory system enabling agent coordination, knowledge retrieval, and full auditability.

---

## Memory Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AGENT ACCESS                                │
├─────────────────┬─────────────────┬────────────────┬────────────────┤
│  Layer 1        │  Layer 2        │  Layer 3       │  Layer 4       │
│  SHORT-TERM     │  GENOMIC        │  VECTOR        │  AUDIT         │
│  EXECUTION      │  KNOWLEDGE      │  RETRIEVAL     │  MEMORY        │
│                 │                 │                │                │
│  Current run    │  Reference      │  Semantic      │  Immutable     │
│  state, inter-  │  databases,     │  search over   │  decision log  │
│  mediate results│  validated facts│  literature    │  with provenance│
├─────────────────┼─────────────────┼────────────────┼────────────────┤
│  Redis/In-mem   │  MongoDB        │  Qdrant        │  Append-only   │
│  TTL: per-run   │  TTL: permanent │  TTL: permanent│  TTL: permanent│
└─────────────────┴─────────────────┴────────────────┴────────────────┘
```

---

## Layer 1: Short-Term Execution Memory

**Purpose:** Holds transient state for the current execution run.

| Content | Lifetime | Access Pattern |
|---------|----------|----------------|
| Current DAG state | Per-run | Read/write by orchestrator |
| Intermediate agent results | Per-run | Write by agents, read by dependents |
| Query context and parameters | Per-run | Read by all agents |
| Checkpoint snapshots | Per-run + persist on completion | Write by orchestrator |

**Implementation:** In-memory store (Redis or Python dict for single-node).

**Eviction:** Cleared after run completion. Final state archived to audit layer.

---

## Layer 2: Genomic Knowledge Memory

**Purpose:** Persistent store of validated pharmacogenomic facts.

| Content | Source | Update Frequency |
|---------|--------|-----------------|
| CPIC guidelines | CPIC database | Quarterly |
| DPWG recommendations | DPWG | Quarterly |
| PharmGKB annotations | PharmGKB | Monthly |
| Allele frequency tables | gnomAD, 1000 Genomes | Per-release |
| Gene-drug interaction mappings | Curated | On change |
| Star allele definitions | PharmVar | Per-release |

**Implementation:** MongoDB collections with versioned documents.

**Access:** Deterministic lookup only. No generative reasoning against this layer.

**Schema:**

```python
@dataclass
class GenomicFact:
    fact_id: str
    category: str          # "interaction", "frequency", "guideline", "allele"
    gene: str
    content: dict          # Structured fact payload
    source: str            # Database/publication source
    version: str           # Source version
    last_updated: datetime
    confidence: float      # 1.0 for validated facts
```

---

## Layer 3: Vector Retrieval Memory

**Purpose:** Semantic search over unstructured genomic literature and knowledge.

| Content | Embedding Model | Chunk Strategy |
|---------|----------------|----------------|
| Research papers | text-embedding-3-small | 512 tokens, 50 overlap |
| Clinical guidelines (full text) | text-embedding-3-small | 1024 tokens, 100 overlap |
| Case reports | text-embedding-3-small | 512 tokens |
| Prior reasoning chains | text-embedding-3-small | Full chain as single doc |

**Implementation:** Qdrant vector database.

**Access pattern:**
1. Retrieval agent receives query
2. Embeds query
3. Searches Qdrant with metadata filters (gene, population, drug)
4. Returns top-k passages with scores and source attribution

**Metadata schema:**

```json
{
  "source": "PMID:12345678",
  "gene": "CYP2D6",
  "population": "EAS",
  "document_type": "research_paper",
  "year": 2023
}
```

---

## Layer 4: Audit Memory

**Purpose:** Immutable, append-only log of every decision and data access.

| Event Type | Logged Data |
|------------|-------------|
| `AGENT_TASK_START` | agent_id, task, timestamp, inputs |
| `AGENT_TASK_COMPLETE` | agent_id, result, duration, confidence |
| `AGENT_TASK_FAIL` | agent_id, error, stack trace |
| `MEMORY_READ` | agent_id, layer, query, results_count |
| `MEMORY_WRITE` | agent_id, layer, key, value_hash |
| `VERIFICATION_PASS` | verifier_id, target_agent, checks_passed |
| `VERIFICATION_FAIL` | verifier_id, target_agent, reason |
| `CONSENSUS_FORMED` | correlation_id, contributing_agents, final_output_hash |

**Implementation:** Append-only log (MongoDB capped collection or file-based JSONL).

**Guarantees:**
- Never modified after write
- Indexed by correlation_id for full trace reconstruction
- Retained indefinitely for reproducibility

---

## Cross-Layer Access Rules

| Agent Type | Layer 1 | Layer 2 | Layer 3 | Layer 4 |
|------------|---------|---------|---------|---------|
| Orchestrator | R/W | R | — | W |
| Population | R/W | R | — | W |
| Chromosome | R/W | R | — | W |
| Pharmacogene | R/W | R | R | W |
| Retrieval | R | R | R | W |
| Verification | R | R | R | W |
| Narrative | R | — | — | W |

R = Read, W = Write, R/W = Read and Write, — = No access
