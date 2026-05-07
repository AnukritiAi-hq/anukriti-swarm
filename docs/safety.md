# Safety Considerations

> Hallucination prevention, grounding, auditability, and explainability in Anukriti Swarm.

---

## Safety Philosophy

Anukriti Swarm operates on genomic data where incorrect outputs could mislead researchers. The safety architecture ensures:

1. **No unsupported claims** — Every output traces to verifiable sources
2. **Explicit uncertainty** — Confidence levels are always communicated
3. **Fail-safe defaults** — When uncertain, return only deterministic facts
4. **Full reproducibility** — Any output can be regenerated from audit trail

---

## 1. Hallucination Prevention

### Structural Safeguards

```
┌─────────────────────────────────────────────────────────────┐
│                 ANTI-HALLUCINATION STACK                     │
├─────────────────────────────────────────────────────────────┤
│  Layer 5: Output labeling ([ESTABLISHED] vs [INFERRED])     │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: Verification agent cross-check                    │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Mandatory grounding (no LLM without facts)        │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Deterministic-first resolution                    │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Constrained prompts (low temperature, structured) │
└─────────────────────────────────────────────────────────────┘
```

### Prevention Mechanisms

| Mechanism | Implementation |
|-----------|---------------|
| Deterministic-first | Always resolve via database before LLM |
| Grounded generation | LLM receives only verified facts as context |
| Low temperature | 0.1–0.3 for factual synthesis tasks |
| Structured output | JSON schema enforcement on LLM responses |
| Source requirement | Every claim must cite a specific source |
| Verification gate | Independent agent validates all generative output |
| Confidence threshold | Reject outputs below 0.7 confidence |

### Known Hallucination Risks

| Risk | Scenario | Mitigation |
|------|----------|------------|
| Fabricated interactions | LLM invents drug-gene interaction | Cross-check against CPIC/PharmGKB |
| Wrong frequency | LLM states incorrect allele frequency | Deterministic lookup, never generated |
| Misattribution | LLM cites non-existent paper | Verify PMID exists via PubMed MCP |
| Phenotype confusion | LLM assigns wrong metabolizer status | Rule-based assignment, never LLM |
| Population conflation | LLM mixes population-specific data | Population-isolated agent contexts |

---

## 2. Grounding Strategy

### Grounding Requirements by Agent

| Agent | Grounding Source | Enforcement |
|-------|-----------------|-------------|
| Pharmacogene (generative) | CPIC guidelines + PharmGKB | Must cite guideline ID |
| Population (generative) | gnomAD frequencies + literature | Must cite population + frequency |
| Narrative | All upstream verified findings | Must reference finding IDs |
| Verification | Multiple independent sources | Must show ≥2 concordant sources |

### Grounding Protocol

```
1. Deterministic agents produce FACTS (sourced, versioned)
         │
         ▼
2. Facts assembled as GROUNDING CONTEXT
         │
         ▼
3. Generative agent receives ONLY grounding context + query
         │
         ▼
4. LLM output MUST reference items from grounding context
         │
         ▼
5. Verification agent checks references are valid
         │
         ▼
6. Ungrounded claims are STRIPPED from output
```

---

## 3. Auditability

### Audit Trail Completeness

Every execution produces a complete audit trail enabling:

| Capability | Mechanism |
|------------|-----------|
| Full replay | Re-execute any query from audit log |
| Decision tracing | Follow any output back to source data |
| Failure analysis | Identify exactly where and why errors occurred |
| Version tracking | Know which database versions produced each result |
| Temporal queries | "What would this result have been on date X?" |

### Audit Record Structure

```
Query Q1 (correlation_id: abc-123)
├── INGEST: VCF parsed, 847 pharmacogene variants
├── ROUTE: Dispatched to [chr10, chr22, population_EAS]
├── CHR10_AGENT: CYP2D6 *1/*4 identified (source: PharmVar 6.0)
├── CHR22_AGENT: CYP2C19 *1/*1 identified (source: PharmVar 6.0)
├── PHARMA_AGENT: Intermediate metabolizer (source: CPIC 2023)
├── POPULATION_AGENT: *4 freq in EAS = 0.01 (source: gnomAD v4)
├── RETRIEVAL: 5 papers retrieved, top relevance 0.92
├── VERIFY: All checks passed (5/5)
├── NARRATIVE: Report generated, confidence 0.89
└── COMPLETE: Total time 34s, all outputs verified
```

### Retention Policy

| Data | Retention | Storage |
|------|-----------|---------|
| Audit logs | Indefinite | Append-only MongoDB |
| Agent outputs | Indefinite | Linked to audit |
| Intermediate state | 30 days | Redis → archive |
| Raw LLM responses | Indefinite | Linked to audit |

---

## 4. Explainability

### Output Explanation Levels

| Level | Audience | Content |
|-------|----------|---------|
| Summary | Researcher (quick) | Key findings with confidence |
| Detailed | Researcher (deep) | Full reasoning chain with sources |
| Technical | Developer/auditor | Raw agent outputs, prompts, scores |
| Trace | Debugging | Complete execution DAG with timings |

### Explanation Components

Every output includes:

```json
{
  "finding": "CYP2D6 Intermediate Metabolizer",
  "confidence": 0.95,
  "source_type": "deterministic",
  "explanation": {
    "reasoning": "Diplotype *1/*4 maps to IM per CPIC translation table",
    "sources": ["CPIC:CYP2D6:2023", "PharmVar:CYP2D6:6.0"],
    "population_context": "EAS: *4 frequency 0.01 (uncommon)",
    "limitations": ["Based on detected variants only; undetected variants may alter result"],
    "alternatives_considered": ["PM classification rejected: requires two no-function alleles"]
  }
}
```

---

## 5. Safety Boundaries

### Hard Limits (Never Violated)

- ❌ Never present generative output as established fact
- ❌ Never omit confidence scores
- ❌ Never skip verification for generative outputs
- ❌ Never provide clinical recommendations (research only)
- ❌ Never generate without grounding context

### Soft Limits (Configurable)

- Confidence threshold (default 0.7, adjustable per research context)
- Maximum generative content ratio (default 30% of report)
- Evidence recency requirement (default: prefer last 5 years)
- Minimum source count for claims (default: 2 concordant sources)

---

## 6. Failure Modes & Recovery

| Failure | Detection | Response |
|---------|-----------|----------|
| LLM hallucination | Verification agent | Strip claim, log, return deterministic only |
| Source not found | Retrieval agent returns empty | Note evidence gap in output |
| Conflicting sources | Verification detects contradiction | Report both with confidence |
| Agent timeout | Orchestrator timeout | Retry once, then skip with note |
| Database stale | Version check on startup | Warn in output, proceed with available |
