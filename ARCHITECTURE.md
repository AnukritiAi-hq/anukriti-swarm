# Architecture

> **Research platform.** Not for clinical use.

This describes what is **actually built** in `anukriti-swarm` today. For
forward-looking roadmap items see `ROADMAP.md`. For per-subsystem design
docs see [`architecture/`](architecture/).

---

## System philosophy

Anukriti Swarm separates genomic intelligence into two execution modes
with a hard runtime boundary:

| Mode | Purpose | Implementation |
|------|---------|----------------|
| **Deterministic** | Phenotype calling, CPIC lookup, allele frequency retrieval, evidence sufficiency rules, verification engines | Rule tables, closed-enum contracts, versioned library ([`anukriti-pgx-core==0.2.1`](https://pypi.org/project/anukriti-pgx-core/)) |
| **Generative** | Narrative synthesis, comparative reasoning, orchestration planning | LLM calls (Gemini or OpenAI), guarded by `GenerativeBoundary` — four forbidden actions (infer_phenotype, override_recommendation, bypass_verification, fabricate_claim) raise at runtime |

The separation is enforced **at the type boundary** — deterministic
outputs are frozen Pydantic records; the generative boundary checks
them via runtime asserts before the LLM can produce narrative. Drift
into "LLM decides" territory requires a deliberate code change, never a
config toggle.

---

## Actual technology stack

| Layer | Technology | Why |
|-------|------------|-----|
| Language | Python 3.11+ | Type hints, frozen dataclasses, `typing_extensions` support |
| Deterministic core | [`anukriti-pgx-core`](https://pypi.org/project/anukriti-pgx-core/) pinned to `0.2.1` | Published library, CPIC tables versioned by filename, zero runtime deps |
| Data models | `pydantic==2.7.1` | Frozen records, closed-enum validation, JSON serialization |
| LLM providers | `google-genai`, `openai==1.30.1`, `anthropic==0.25.8` | Multi-provider with fallback; Gemini is primary |
| Backend API | `fastapi==0.111.0` + `uvicorn==0.29.0` | WebSocket streaming for live execution events |
| WebSocket | `websockets==15.0.1` | `/ws/run` endpoint for per-event UI updates |
| Persistence | `pymongo==4.17.0` (optional, falls back to in-memory) | MCP layer writes to MongoDB Atlas when `MONGODB_URI` is set |
| Frontend | Vanilla JS + D3 v7.9.0 (vendored) | No build step, no npm — D3 only used for the force-directed graph view |
| Dev tooling | `pytest==8.2.0`, `ruff==0.4.4`, `mypy==1.10.0` | Progressive ruff hard-gate (see `.project-status.md` sessions #9–#11) |

**What we don't depend on:** `langchain` / `langgraph` (agent framework
is hand-rolled in `core/orchestrator/` + `agents/`), and `qdrant-client`
(retrieval uses in-tree TF-IDF via `retrieval/indexing/embeddings.py`;
a vector-DB swap is a one-file change behind the `BiomedicalRetriever`
ABC). Historical docstrings and doc files still mention "LangGraph-
style" / "Qdrant-compatible" patterns — those describe the *shape* of
the code (state graph, vector-search-compatible interface), not a
runtime dependency.

---

## What's built — module map

```
anukriti-swarm/
├── agents/                    Specialist agents (9 in the catalog)
│   ├── orchestrator/          GeminiOrchestrator facade
│   ├── pharmacogene/          CYP2D6, CYP2C19, HLA-B specialists
│   ├── verification/          BiomedicalVerificationAgent
│   ├── evidence/              ContextSufficiencyAgent (session #6)
│   └── registry/              Agent discovery + routing
│
├── core/
│   ├── orchestrator/          ExecutionCoordinator, Router, Planner, ConflictResolver
│   ├── evidence_sufficiency/  6-facet coverage · 12 R-rules · 10 V-rules · 9 U-rules · 3 bias kinds
│   ├── verification/          4 safety engines (shape · existence · truth · chain)
│   ├── runtime/               SwarmRuntime + UnifiedExecutionContext + RuntimeEvent
│   └── models/                Closed-enum Pydantic domain records
│
├── knowledge_graph/           PharmacogenomicKG (37 nodes / 34 edges · 10 NodeKinds · 7 EdgeKinds)
├── retrieval/                 Multi-strategy retrievers + adaptive controller + stopping controller
├── interoperability/          A2A envelope + agent bus + shared context + provenance propagation
├── integrations/mcp/          6 MCP services · 31 tools · auto-persistence · replay
│
├── backend/                   FastAPI app + /api/run + /ws/run + RunCache + snapshots
├── frontend/                  Vanilla JS + D3 live mission-control UI
│
├── evaluation/                6 suites + 4 stress + 3 ancestry scenarios
├── benchmarks/                12 pinned regression scenarios (3 genes × 4 populations)
│
├── observability/             ExecutionTracer + TimingProfiler + AgentActivityMonitor
├── visualization/             ANSI trace renderer + D3 flow graphs
│
├── demos/                     29 runnable demos (showcase, safety, unified, sufficiency, …)
└── tests/                     234 pytest tests (unit + integration)
```

---

## Runtime flow

```
        Input: (drug, gene, population, genotype)
                        │
                        ▼
        ┌───────────────────────────────┐
        │   SwarmRuntime.run()          │  single 5-stage lifecycle
        │   (core/runtime/runtime.py)   │  emits 12 closed RuntimeEventKinds
        └───────┬───────────────────────┘
                │
                ▼
   Stage 1. Context assembly  ──▶ SwarmExecutionContext (Pydantic, frozen)
                │
                ▼
   Stage 2. Orchestration     ──▶ planner (Gemini + deterministic fallback)
                │                   ├── router (specialist assignment)
                │                   └── coordinator (pipeline execution)
                │
                ▼
   Stage 3. Retrieval         ──▶ multi-strategy retrievers
                │                   (dense · population-aware · KG · diversity selector)
                │
                ▼
   Stage 3.5. Sufficiency     ──▶ SufficiencyCheckpoint  (OPT-IN, default None)
                │                   ├── 6-facet coverage analyzer
                │                   ├── 12-rule decision engine
                │                   ├── 10-rule verifier (SURE-RAG-style)
                │                   ├── 9-rule uncertainty scorer
                │                   └── 3-kind bias detector
                │
                ▼
   Stage 4. Verification      ──▶ 4 safety engines:
                │                   ├── BiomedicalClaimValidator  (shape)
                │                   ├── EvidenceGroundingEngine    (existence)
                │                   ├── SafetyConstraintEngine     (truth)
                │                   └── ProvenanceValidator        (chain)
                │
                ▼
   Stage 5. Synthesis         ──▶ NarrativeGenerator (guarded by GenerativeBoundary)
                │
                ▼
        UnifiedExecutionReport (frozen · 18 fields · JSON-serializable)
                │
                ▼
  MCP persistence (if enabled): memory · traces · context · provenance · evidence · verification
```

Every stage emits `RuntimeEvent`s with a frozen 12-kind `RuntimeEventKind`
enum. The `/ws/run` endpoint streams these live to the frontend for
per-event panel updates.

---

## Key design invariants

1. **No clinical decisions.** Outputs are research artifacts; the
   system is positioned as a research platform, not a clinical tool.
2. **Deterministic first.** Rule tables always run before any LLM call.
   Closed-enum contracts make drift a review-time catch.
3. **Population is reasoning context, not metadata.** `SuperPopulation`
   is a first-class closed enum; allele frequencies are KG edges with
   explicit weights; bias detection has concrete numeric thresholds.
4. **Every claim has provenance.** The MCP `MCPProvenanceStore` walks
   `narrative → recommendation → phenotype → CPIC rule → evidence`
   in one call. Every edge in the KG requires a non-empty
   `ProvenanceStamp.source_id`.
5. **Off-by-default for new capabilities.** The sufficiency checkpoint
   (session #6) and the unified runtime (session #7) integrate via
   explicit constructor args defaulting to `None`. Flagship demo
   signatures are byte-identical pre-and-post.
6. **Every refusal is named.** Abstentions and blocks cite a specific
   rule ID (R1..R12, V1..V10, U1..U9, or named bias kind).

---

## Consumer relationship with `anukriti-pgx-core`

`anukriti-pgx-core` owns the deterministic biomedical truth layer. Swarm
consumes it via a pinned PyPI dependency (`anukriti-pgx-core==0.2.1`)
and re-exports the phenotype engine through `rules/phenotype_rules.py`.

When pgx-core releases a new version:
1. Read `anukriti-pgx-core/CHANGELOG.md` for the release notes.
2. Check if any CPIC tables changed; read the diff.
3. Run the swarm regression gate against the new version in a branch.
4. If byte-identical, bump the pin in `requirements.txt` in a small PR.
5. If behavior changed, the PR must document the diff and update
   benchmarks that surface the new call.

The contract is documented in
[`../anukriti-pgx-core/PROJECT_CONTEXT.md`](https://github.com/AnukritiAi-hq/anukriti-pgx-core/blob/main/PROJECT_CONTEXT.md#regression-contract-byte-identical-across-all-11-commits).

---

## CI and quality gates

Every push and PR runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

| Job | What | Gate |
|-----|------|------|
| `test` | pytest matrix on Python 3.11 + 3.12 — full 234 tests + legacy regression | Hard (blocks merge) |
| `lint` | ruff check + format on `tests/` + `core/runtime/` + `core/evidence_sufficiency/` (hard); informational on rest | Hard gate on covered dirs |
| `demos` | 7 flagship demos invoked individually with 60s timeouts | Hard (blocks merge) |

Ruff hard-gate adoption is **progressive** — new directories get
promoted from the informational debt report to the hard gate via
small cleanup PRs. Session #11 promoted `core/evidence_sufficiency/`;
next candidate directories are listed in `.project-status.md`.

---

## Agent taxonomy

### Orchestrator
`GeminiOrchestrator` (`agents/orchestrator/gemini_orchestrator.py`) —
single-entry facade. Methods: `run(query)`, `compare_populations(...)`,
`compare_drugs(...)`. Composes context assembler → planner → router →
coordinator.

### Specialist agents
| Agent | Role |
|-------|------|
| Population agents (SAS / AFR / EUR) | Ancestry-specific frequency lookup, Hardy-Weinberg prevalence, rarity classification |
| Pharmacogene agents (CYP2D6 / CYP2C19 / HLA-B) | Star-allele and HLA variant interpretation |
| Evidence retrieval | MA-RAG: query planning, TF-IDF retrieval, citation extraction |
| Verification | 4-engine composition (shape · existence · truth · chain) |
| Sufficiency | ContextSufficiencyAgent orchestrates 4 layers (coverage · decision · verifier · uncertainty) |
| Narrative | Audience-specific report generation (clinician · patient · researcher · audit) |

### Communication
Agents never call each other directly. They communicate via:
- `AgentMessageBus` (typed pub/sub with closed-enum context types)
- `SharedBiomedicalContext` (append-only shared state)
- `AgentContextEnvelope` (frozen 7-field message, `BiomedicalContextType` enum enforces scope)

See [`architecture/interoperability.md`](architecture/interoperability.md).

---

## Further reading

Per-subsystem design docs live in [`architecture/`](architecture/):

| Doc | Subject |
|-----|---------|
| `unified-runtime.md` | SwarmRuntime + UnifiedExecutionReport + event stream |
| `backend-api.md` | FastAPI + WebSocket + RunCache |
| `evidence-sufficiency.md` | Session #6 sufficiency layer |
| `pharmacogenomic-kg.md` | KG schema + traversal + population weighting |
| `interoperability.md` | A2A envelope + bus + shared context |
| `evaluation-framework.md` | 6 suites + stress + ancestry scenarios |
| `observability-visualization.md` | Tracing + metrics + cinematic mode |
| `verification-safety.md` | 4 safety engines |
| `mcp-infrastructure.md` | 6 services + 31 tools + replay |
| `gemini-orchestration.md` | Orchestrator + boundary + deterministic-first |

The living session log is [`.project-status.md`](.project-status.md).

Non-obvious decisions that cross the repo boundary go in
[`../anukriti-pgx-core/docs/adr/`](../anukriti-pgx-core/docs/adr/).
