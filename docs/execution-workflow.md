# Execution Workflow

> End-to-end pipeline: VCF input → orchestration → genomic analysis → evidence retrieval → verification → narrative output.

---

## Pipeline Overview

```
┌───────┐   ┌──────────────┐   ┌──────────────┐   ┌────────────┐   ┌──────────────┐   ┌───────────┐
│  VCF  │──▶│ ORCHESTRATE  │──▶│   ANALYZE    │──▶│  RETRIEVE  │──▶│   VERIFY     │──▶│ NARRATIVE │
│ Input │   │              │   │  (genomic)   │   │ (evidence) │   │              │   │  Output   │
└───────┘   └──────────────┘   └──────────────┘   └────────────┘   └──────────────┘   └───────────┘
```

---

## Stage 1: VCF Ingestion

**Agent:** Orchestrator (via Dataset MCP)

| Step | Action | Output |
|------|--------|--------|
| 1.1 | Parse VCF file | Structured variant records |
| 1.2 | Validate format and quality | QC report, filtered variants |
| 1.3 | Extract sample metadata | Population hint, sample ID |
| 1.4 | Partition by chromosome | Per-chromosome variant sets |

**Output schema:**
```json
{
  "sample_id": "SAMPLE_001",
  "reference_genome": "GRCh38",
  "total_variants": 4200000,
  "pharmacogene_variants": 847,
  "chromosomes_with_variants": ["chr1", "chr2", "chr10", "chr22"],
  "quality_pass_rate": 0.97
}
```

---

## Stage 2: Orchestration & DAG Compilation

**Agent:** Orchestrator

| Step | Action | Output |
|------|--------|--------|
| 2.1 | Identify relevant pharmacogenes | Gene list for analysis |
| 2.2 | Determine population context | Population assignment |
| 2.3 | Build execution DAG | Task graph with dependencies |
| 2.4 | Assign agents to nodes | Agent-task mapping |
| 2.5 | Dispatch parallel tasks | Execution begins |

**Decision logic:**
- If population known → assign specific population agent
- If population unknown → run ancestry inference first
- Pharmacogenes with variants → full analysis
- Pharmacogenes without variants → skip (report as wild-type)

---

## Stage 3: Genomic Analysis

**Agents:** Chromosome Agents + Pharmacogene Agents (parallel)

### 3a. Chromosome-Level Analysis

| Step | Action | Mode |
|------|--------|------|
| 3a.1 | Map variants to genes | Deterministic |
| 3a.2 | Annotate functional impact | Deterministic |
| 3a.3 | Identify haplotypes | Deterministic |
| 3a.4 | Flag novel variants | Deterministic (flag only) |

### 3b. Pharmacogene Analysis

| Step | Action | Mode |
|------|--------|------|
| 3b.1 | Assign star alleles | Deterministic |
| 3b.2 | Determine diplotype | Deterministic |
| 3b.3 | Classify metabolizer phenotype | Deterministic |
| 3b.4 | Lookup drug interactions | Deterministic |
| 3b.5 | Retrieve dosage guidelines | Deterministic |

### 3c. Population Contextualization

| Step | Action | Mode |
|------|--------|------|
| 3c.1 | Lookup population allele frequencies | Deterministic |
| 3c.2 | Compare to global frequencies | Deterministic |
| 3c.3 | Flag population-specific considerations | Deterministic |

**Stage 3 output:** Structured pharmacogenomic findings per gene.

---

## Stage 4: Evidence Retrieval

**Agent:** Retrieval Agent

| Step | Action | Mode |
|------|--------|------|
| 4.1 | Search vector DB for supporting literature | Deterministic |
| 4.2 | Retrieve relevant CPIC/DPWG guideline sections | Deterministic |
| 4.3 | Find population-specific studies | Deterministic |
| 4.4 | Rank evidence by relevance and recency | Deterministic |

**Output:** Ranked evidence passages with source attribution, linked to specific findings.

---

## Stage 5: Verification

**Agent:** Verification Agent

| Step | Action | Failure Mode |
|------|--------|-------------|
| 5.1 | Cross-check star alleles against PharmVar | Reject if mismatch |
| 5.2 | Validate phenotype-genotype consistency | Reject if inconsistent |
| 5.3 | Confirm guideline applicability | Flag if outdated |
| 5.4 | Check population frequency plausibility | Flag if outlier |
| 5.5 | Verify evidence supports conclusions | Reject if unsupported |

**Gate:** Only verified findings proceed to narrative generation.

---

## Stage 6: Narrative Generation

**Agent:** Narrative Agent

| Step | Action | Mode |
|------|--------|------|
| 6.1 | Synthesize findings into structured report | Generative |
| 6.2 | Generate plain-language explanations | Generative |
| 6.3 | Assemble citations and references | Deterministic |
| 6.4 | Apply confidence labels to each section | Deterministic |
| 6.5 | Format final output | Deterministic |

**Output structure:**
```
┌─────────────────────────────────────────┐
│ PHARMACOGENOMIC ANALYSIS REPORT         │
├─────────────────────────────────────────┤
│ Summary (generative, verified)          │
├─────────────────────────────────────────┤
│ Per-Gene Findings                       │
│  • Gene: CYP2D6                         │
│  • Diplotype: *1/*4 [ESTABLISHED]       │
│  • Phenotype: Intermediate Metabolizer  │
│  • Drugs Affected: [list]               │
│  • Population Context: [ESTABLISHED]    │
│  • Clinical Implication: [INFERRED]     │
├─────────────────────────────────────────┤
│ Evidence & References                   │
├─────────────────────────────────────────┤
│ Limitations & Confidence                │
├─────────────────────────────────────────┤
│ Audit Trail (correlation_id link)       │
└─────────────────────────────────────────┘
```

---

## End-to-End Timing Targets

| Stage | Target Latency | Parallelism |
|-------|---------------|-------------|
| VCF Ingestion | < 5s | Single |
| DAG Compilation | < 1s | Single |
| Genomic Analysis | < 30s | Per-chromosome |
| Evidence Retrieval | < 10s | Per-gene |
| Verification | < 5s | Per-finding |
| Narrative | < 15s | Single |
| **Total** | **< 60s** | — |
