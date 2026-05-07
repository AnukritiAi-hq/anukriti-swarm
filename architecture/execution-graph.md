# Execution Graph Design

> DAG-based execution model for orchestrating multi-agent pharmacogenomic analysis.

---

## Overview

Every query to Anukriti Swarm is compiled into a **Directed Acyclic Graph (DAG)** of agent tasks. The orchestrator builds, validates, and executes this graph, enabling parallel execution where dependencies allow.

---

## Graph Structure

```
                         ┌─────────────┐
                         │   INGEST    │  (VCF parse + validate)
                         └──────┬──────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
             ┌──────────┐ ┌──────────┐ ┌──────────┐
             │  Chr 1   │ │  Chr 2   │ │  Chr N   │  ← parallel
             └────┬─────┘ └────┬─────┘ └────┬─────┘
                  │            │            │
                  └────────────┼────────────┘
                               ▼
                    ┌─────────────────────┐
                    │  PHARMACOGENE       │  (star alleles, phenotypes)
                    └──────────┬──────────┘
                               │
                    ┌──────────┼──────────┐
                    ▼                     ▼
          ┌──────────────────┐  ┌──────────────────┐
          │  POPULATION      │  │  RETRIEVAL       │  ← parallel
          │  (freq context)  │  │  (evidence)      │
          └────────┬─────────┘  └────────┬─────────┘
                   │                     │
                   └──────────┬──────────┘
                              ▼
                   ┌─────────────────────┐
                   │   VERIFICATION      │
                   └──────────┬──────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │   NARRATIVE         │
                   └─────────────────────┘
```

---

## DAG Node Definition

```python
@dataclass
class DAGNode:
    node_id: str
    agent_type: AgentType
    task: AgentTask
    dependencies: list[str]       # node_ids that must complete first
    status: NodeStatus            # PENDING | READY | RUNNING | DONE | FAILED
    result: AgentResult | None
    timeout_seconds: int
    retry_count: int = 0
    max_retries: int = 2
```

---

## Execution Semantics

### Node States

```
PENDING ──(deps satisfied)──▶ READY ──(dispatched)──▶ RUNNING
                                                          │
                                          ┌───────────────┼───────────────┐
                                          ▼               ▼               ▼
                                        DONE           FAILED          TIMEOUT
                                                         │               │
                                                         ▼               ▼
                                                      RETRY?          RETRY?
                                                      (≤ max)         (≤ max)
                                                         │               │
                                                    yes: READY      yes: READY
                                                    no:  ESCALATE   no:  ESCALATE
```

### Scheduling Rules

1. A node becomes READY when all its dependencies are DONE
2. READY nodes are dispatched in priority order
3. Independent nodes execute in parallel
4. Failed nodes block downstream dependents
5. ESCALATE triggers orchestrator intervention (skip, retry with different params, or abort)

---

## Graph Compilation

The orchestrator compiles a query into a DAG through:

| Step | Action |
|------|--------|
| 1. Parse | Extract query intent, VCF data, population context |
| 2. Plan | Determine which agents are needed |
| 3. Dependency analysis | Identify data flow between agents |
| 4. Parallelize | Group independent tasks for concurrent execution |
| 5. Validate | Ensure DAG is acyclic and all dependencies are satisfiable |
| 6. Emit | Produce executable DAG with timeouts and retry policies |

---

## Execution Strategies

### Full Analysis (default)

All agents activated. Maximum parallelism at chromosome level.

### Targeted Query

Only relevant agents activated (e.g., single gene lookup skips chromosome fan-out).

### Incremental

Resume from checkpoint — re-execute only failed or updated nodes.

---

## Checkpointing

After each node completes:
- Result written to memory layer
- DAG state persisted
- Audit entry created

This enables:
- Resume after failure
- Partial result inspection
- Execution replay for debugging

---

## Concurrency Limits

| Agent Type | Max Parallel Instances |
|------------|----------------------|
| Chromosome | 24 (one per chromosome) |
| Population | 5 (one per super-population) |
| Pharmacogene | 3 |
| Retrieval | 5 |
| Verification | 2 |
| Narrative | 1 |
