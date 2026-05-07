# System Design: Architecture Rationale and Tradeoffs

> Technical report documenting the design decisions behind Anukriti Swarm.

---

## 1. Why Multi-Agent?

### Decision

Decompose pharmacogenomic reasoning into specialized agents rather than using a single monolithic model.

### Rationale

| Factor | Monolithic | Multi-Agent (chosen) |
|--------|-----------|---------------------|
| Expertise depth | Shallow across all domains | Deep per domain |
| Failure isolation | One failure breaks everything | Failed agent doesn't block others |
| Testability | Black box | Each agent independently testable |
| Extensibility | Retrain entire model | Add new agent, no changes to existing |
| Auditability | Opaque reasoning | Per-agent provenance trail |

### Tradeoff

Multi-agent adds coordination complexity. We mitigate this with a simple orchestrator and message-passing through shared state (LangGraph pattern).

---

## 2. Why Deterministic/Generative Separation?

### Decision

Enforce a strict boundary: established pharmacogenomic facts are computed deterministically; only explanations and novel hypotheses use generative models.

### Rationale

Pharmacogenomics has a well-defined knowledge base (CPIC, PharmVar, gnomAD). For established science:
- Star allele → phenotype mapping is a **lookup table**, not a reasoning task
- Activity scores are **arithmetic**, not inference
- Guideline recommendations are **conditional rules**, not generation

Using an LLM for these tasks introduces hallucination risk with zero benefit.

### Tradeoff

Template-based narratives are less fluent than LLM-generated text. We accept this tradeoff because:
1. Correctness > fluency in pharmacogenomics
2. LLM narrative can be added later (in the generative layer, behind verification)
3. Every claim remains traceable to its deterministic source

---

## 3. Why Population-First Architecture?

### Decision

Make population context a required input that influences every stage of reasoning, not an optional annotation.

### Rationale

The same genotype has different clinical significance by population:
- CYP2D6*4 at 22% in EUR is "expected" — guidelines are validated here
- CYP2D6*4 at 2% in AFR is "unusual" — may warrant genotyping verification
- CYP2C19*2 at 36% in SAS means 14% are PMs — a population health crisis

Systems that ignore population context perpetuate health inequities by applying EUR-validated guidelines universally.

### Tradeoff

Requires population data for every query. When population is unknown, the system must either:
1. Infer ancestry from variants (future: PCA-based)
2. Report results for all populations with appropriate caveats
3. Flag as "population context missing" with reduced confidence

---

## 4. Why Verification Gate?

### Decision

No output reaches the user without passing 6 verification checks and TAO escalation assessment.

### Rationale

In healthcare-adjacent AI, false confidence is more dangerous than acknowledged uncertainty. The verification gate ensures:
- Ungrounded claims are stripped
- Low-confidence outputs are flagged
- Contradictions are surfaced
- Sparse data triggers warnings

### Tradeoff

Adds latency (~0.1ms in current implementation). Acceptable given the safety benefit. May reject valid outputs if verification rules are too strict — we prefer false negatives (withholding information) over false positives (delivering unverified claims).

---

## 5. Why MA-RAG for Retrieval?

### Decision

Use a multi-step retrieval pipeline (plan → sub-queries → retrieve → cite → synthesize) rather than single-shot RAG.

### Rationale

Pharmacogenomic queries have multiple information needs:
- Guideline recommendation (CPIC)
- Mechanism explanation (PharmGKB)
- Population context (gnomAD/literature)
- Supporting evidence (PubMed)

Single-shot RAG conflates these needs. MA-RAG decomposes the query into targeted sub-queries, each routed to the appropriate source.

### Tradeoff

More complex than single-shot RAG. Justified because:
1. Each sub-query can be independently verified
2. Citations are precise (per-claim, not per-response)
3. Grounding score is computable (fraction of claims with citations)

---

## 6. Scalability Considerations

### Current: Single-Process

All agents run in-process, sequentially. Adequate for demo and research.

### Future: Distributed

| Component | Scaling Strategy |
|-----------|-----------------|
| Chromosome agents | Parallel (up to 25 concurrent) |
| Population agents | One per population (5 instances) |
| Retrieval | Co-located with vector DB |
| Verification | Stateless, horizontally scalable |
| Orchestrator | Single leader with failover |

### Bottlenecks

| Bottleneck | Current | Future Mitigation |
|-----------|---------|-------------------|
| LLM calls | None (deterministic) | Rate limiting, caching |
| Vector search | In-memory TF-IDF | Qdrant cluster |
| Frequency lookup | In-memory dict | MongoDB with indexes |
| VCF parsing | Not implemented | Stream parsing, chromosome partitioning |

---

## 7. Technology Choices

| Choice | Rationale |
|--------|-----------|
| Python 3.11+ | Type safety, ecosystem, team familiarity |
| Pydantic | Validated domain models, serialization |
| LangGraph pattern | State graph execution, checkpointing |
| Frozen dataclasses | Immutable messages, audit safety |
| No external deps for core | Runs offline, reproducible |
| MCP-ready interfaces | Future tool server integration |

---

## 8. What We Chose NOT To Do

| Decision | Reason |
|----------|--------|
| No real LLM calls | Deterministic core doesn't need them; adds cost and non-determinism |
| No database | In-memory data sufficient for research demo |
| No authentication | Research prototype, not production service |
| No async | Sequential execution is simpler and sufficient at current scale |
| No microservices | Single-process is adequate; distributed is future work |
| No clinical validation | Explicitly out of scope — research only |

---

*This document records architectural decisions for the Anukriti Swarm research prototype.*
