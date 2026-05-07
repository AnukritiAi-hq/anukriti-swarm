# Deterministic vs Generative Boundary

> Defines the strict separation between factual computation and LLM-based reasoning in Anukriti Swarm.

---

## Core Principle

```
┌─────────────────────────────────────────────────────────────────┐
│                    DETERMINISTIC LAYER                           │
│  "What is known" — database lookups, validated rules, math      │
│  ─────────────────────────────────────────────────────────────  │
│  • Zero hallucination risk                                      │
│  • Reproducible outputs                                         │
│  • Source-attributed                                            │
├─────────────────────────────────────────────────────────────────┤
│                    BOUNDARY (Verification Gate)                  │
├─────────────────────────────────────────────────────────────────┤
│                    GENERATIVE LAYER                              │
│  "What might be inferred" — LLM reasoning, hypothesis, narrative│
│  ─────────────────────────────────────────────────────────────  │
│  • Labeled as inference                                         │
│  • Confidence-scored                                            │
│  • Grounded in deterministic outputs                            │
│  • Verified before delivery                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Deterministic Operations

These operations **never** invoke an LLM. They produce identical outputs for identical inputs.

| Operation | Agent | Data Source |
|-----------|-------|-------------|
| Star allele assignment | Pharmacogene | PharmVar definitions |
| Metabolizer phenotype classification | Pharmacogene | CPIC translation tables |
| Allele frequency lookup | Population | gnomAD, 1000 Genomes |
| Known drug-gene interaction | Pharmacogene | CPIC/DPWG/PharmGKB |
| Variant functional annotation | Chromosome | ClinVar, dbSNP |
| Gene coordinate mapping | Chromosome | RefSeq GRCh38 |
| Dosage guideline retrieval | Pharmacogene | CPIC guidelines |
| VCF parsing and validation | Chromosome | VCF spec |

### Deterministic Guarantees

- **Idempotent:** Same input → same output, always
- **Sourced:** Every output carries a source reference
- **Versioned:** Tied to specific database version
- **Cacheable:** Results can be cached indefinitely for same input + version

---

## Generative Operations

These operations invoke LLMs and produce variable outputs. They are **always** grounded in deterministic outputs.

| Operation | Agent | Grounding Required |
|-----------|-------|--------------------|
| Novel interaction hypothesis | Pharmacogene | Known interactions + literature |
| Population-contextualized explanation | Population | Frequency data + guidelines |
| Cross-gene interaction reasoning | Pharmacogene | Individual gene facts |
| Clinical narrative synthesis | Narrative | All verified findings |
| Evidence summarization | Retrieval | Retrieved passages |
| Contradiction resolution | Verification | Conflicting deterministic outputs |

### Generative Constraints

- **Must cite sources:** Every generative claim links to deterministic evidence
- **Confidence-scored:** Output includes model confidence (0.0–1.0)
- **Labeled:** Clearly marked as `[INFERRED]` vs `[ESTABLISHED]`
- **Verified:** Must pass verification agent before reaching user
- **Temperature-controlled:** Low temperature (0.1–0.3) for factual synthesis

---

## Verification Pipeline

```
Deterministic Output ──┐
                       ├──▶ Generative Agent ──▶ Verification Agent ──▶ Output
Grounding Context ─────┘           │                     │
                                   │                     ▼
                                   │              ┌─────────────┐
                                   │              │ PASS: deliver│
                                   │              │ FAIL: reject │
                                   │              └─────────────┘
                                   │
                                   ▼
                          ┌─────────────────┐
                          │ Provenance Log  │
                          │ • Input facts   │
                          │ • Prompt used   │
                          │ • Raw output    │
                          │ • Confidence    │
                          └─────────────────┘
```

### Verification Checks

| Check | Method | Failure Action |
|-------|--------|----------------|
| Factual consistency | Compare claims against deterministic outputs | Reject |
| Source attribution | Verify cited sources exist and support claim | Reject |
| Confidence threshold | Reject if confidence < 0.7 | Reject |
| Contradiction scan | Check against known facts in Layer 2 | Flag for review |
| Scope adherence | Ensure output stays within query scope | Trim |

---

## Boundary Enforcement Rules

1. **Deterministic first** — Always resolve via lookup before invoking LLM
2. **No generative without grounding** — LLM never runs without deterministic context
3. **Explicit labeling** — Every output field is tagged `deterministic` or `generative`
4. **Audit both** — Both layers log to audit memory with full provenance
5. **Fail safe** — If verification fails, return only deterministic results with explanation

---

## Output Labeling Schema

```python
@dataclass
class LabeledOutput:
    content: str
    source_type: Literal["deterministic", "generative"]
    confidence: float              # 1.0 for deterministic, 0.0-1.0 for generative
    sources: list[str]             # Database IDs, PMIDs, guideline refs
    verification_status: str       # "verified", "pending", "failed"
    grounding_facts: list[str]     # Deterministic facts this was built on
```
