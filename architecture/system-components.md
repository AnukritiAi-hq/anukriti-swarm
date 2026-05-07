# System Components

> Defines the 7 core agent types in the Anukriti Swarm architecture.

---

## Agent Registry

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR AGENT                           │
│              (routing · validation · consensus · lifecycle)         │
├────────────┬────────────┬────────────┬────────────┬────────────────┤
│ Population │ Chromosome │ Pharmaco-  │ Retrieval  │ Verification   │
│ Agents     │ Agents     │ gene Agents│ Agents     │ Agents         │
└────────────┴────────────┴────────────┴────────────┴────────────────┘
                                                          │
                                                          ▼
                                                 ┌────────────────┐
                                                 │ Narrative Agent │
                                                 └────────────────┘
```

---

## 1. Orchestrator Agent

**Role:** Central coordinator and execution controller.

| Responsibility | Description |
|----------------|-------------|
| Query routing | Decomposes incoming requests into sub-tasks for specialist agents |
| Lifecycle management | Spawns, monitors, and terminates agent executions |
| Validation gate | Ensures all outputs pass verification before consensus |
| Consensus assembly | Aggregates multi-agent results into unified response |
| DAG execution | Manages execution graph ordering and dependencies |

**Execution mode:** Deterministic (routing logic) + Generative (query decomposition)

---

## 2. Population Agents

**Role:** Population-level genomic intelligence.

| Capability | Mode |
|------------|------|
| Allele frequency lookup by population | Deterministic |
| Ancestry inference from variant profile | Generative |
| Population stratification analysis | Deterministic |
| Cross-population frequency comparison | Deterministic |
| Ethnopharmacogenomic contextualization | Generative |

**Data sources:** gnomAD, 1000 Genomes, population-specific frequency databases.

**Scaling:** One agent instance per population group (e.g., SAS, EAS, AFR, EUR, AMR).

---

## 3. Chromosome Agents

**Role:** Chromosome-level variant analysis and annotation.

| Capability | Mode |
|------------|------|
| Variant parsing from VCF | Deterministic |
| Gene mapping (variant → gene) | Deterministic |
| Functional impact annotation | Deterministic |
| Haplotype phasing | Deterministic |
| Structural variant detection | Generative |

**Scaling:** Parallelizable — one agent per chromosome (chr1–22, chrX, chrY, chrMT).

**Input:** VCF records filtered by chromosome.

---

## 4. Pharmacogene Agents

**Role:** Drug-gene interaction reasoning.

| Capability | Mode |
|------------|------|
| Known interaction lookup (CPIC, DPWG, PharmGKB) | Deterministic |
| Star allele assignment | Deterministic |
| Metabolizer phenotype classification | Deterministic |
| Dosage adjustment recommendation | Deterministic |
| Novel interaction hypothesis | Generative |

**Data sources:** CPIC guidelines, DPWG recommendations, PharmGKB annotations.

**Critical constraint:** All clinical-grade lookups are deterministic. Generative outputs are explicitly labeled as hypotheses.

---

## 5. Retrieval Agents

**Role:** Evidence retrieval from knowledge bases and literature.

| Capability | Mode |
|------------|------|
| Vector similarity search over genomic KB | Deterministic |
| PubMed/literature retrieval | Deterministic |
| Guideline document retrieval | Deterministic |
| Context assembly for downstream agents | Deterministic |

**Integration:** MCP-based tool access to vector stores and document databases.

**Output:** Ranked evidence passages with source attribution and relevance scores.

---

## 6. Verification Agents

**Role:** Output validation and hallucination prevention.

| Capability | Mode |
|------------|------|
| Fact-checking against known databases | Deterministic |
| Cross-reference validation (multi-source) | Deterministic |
| Confidence scoring | Deterministic |
| Contradiction detection | Generative |
| Source provenance verification | Deterministic |

**Position in pipeline:** Runs after every generative agent output, before consensus.

**Failure mode:** If verification fails, output is rejected and flagged for human review.

---

## 7. Narrative Agents

**Role:** Human-readable report generation from structured findings.

| Capability | Mode |
|------------|------|
| Clinical narrative synthesis | Generative |
| Evidence summarization | Generative |
| Confidence communication | Generative |
| Structured report formatting | Deterministic |
| Citation assembly | Deterministic |

**Input:** Verified, structured findings from upstream agents.

**Output:** Research-grade narrative report with citations, confidence levels, and limitations.

**Constraint:** Only operates on verified data. Never generates unsupported claims.

---

## Agent Interface Contract

Every agent implements:

```python
class BaseAgent(Protocol):
    agent_id: str
    agent_type: AgentType
    execution_mode: Literal["deterministic", "generative", "hybrid"]

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute assigned task and return structured result."""
        ...

    async def validate(self, result: AgentResult) -> ValidationResult:
        """Self-validate output before submission."""
        ...
```

---

## Agent Lifecycle States

```
IDLE → ASSIGNED → EXECUTING → VALIDATING → COMPLETE
                                    │
                                    ▼
                                 FAILED → RETRY (max 2) → ESCALATE
```
