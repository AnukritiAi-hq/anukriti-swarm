# Roadmap

> Forward-looking plan for Anukriti Swarm. For what has already shipped,
> see **[`.project-status.md`](.project-status.md)** — the per-session
> log covering sessions #1 through #14 is the single source of truth
> on current state.

---

## Status as of 2026-05-11

The **foundational phases (0-5 in earlier drafts of this roadmap) are
complete.** The research platform has:

- Full 5-stage `SwarmRuntime` lifecycle (session #7)
- 9 core specialist agents + agent bus (sessions #0-#5)
- Deterministic safety engine with 4 verification engines (session #2)
- Evidence sufficiency layer with 15 closed enums, 12+10+9 rules + Method 4 cross-ancestry hedge (sessions #6, #14)
- Pharmacogenomic knowledge graph (37 nodes, 34 edges) + multi-hop reasoner (session #6)
- Multi-strategy retrieval with adaptive stopping (session #6)
- MCP persistence layer: 6 services, 31 tools (sessions #0-#1)
- Live FastAPI backend + WebSocket event stream (session #7)
- Vanilla JS + D3 mission-control frontend (session #7)
- **244 pytest tests** (sessions #8, #14)
- GitHub Actions CI with progressive ruff hard-gate (sessions #9-#11, #13)
- Docker + docker-compose (session #12)
- Stage-1 cohort-scale demo with 16.0× ancestry delta (session #14)
- `core/simulation/` closed-enum scope for cohort reasoning (session #14)

Read the ⭐ Session entries in `.project-status.md` for the commit-
level detail on each of these.

**Frontend note:** earlier drafts of this roadmap planned a Next.js
dashboard. We shipped vanilla JS + D3 (single vendored file, no build
step) instead, because the research surface benefits from being
hackable. See [ARCHITECTURE.md](ARCHITECTURE.md) for the reasoning.

---

## Active open work

Tracked at the bottom of [`.project-status.md`](.project-status.md#whats-not-done-yet-future-work--ordered-by-roi).
Summarized here:

### High-value, short horizon

- [ ] **Progressive ruff hard-gate adoption** — continue the
  session-#11 pattern. Next directories in order: `core/orchestrator/`
  → `knowledge_graph/` → `core/models/` → `core/verification/` →
  `retrieval/` → `observability/`. Each promotion is a small
  reviewable PR and an ideal new-contributor entry point.
- [ ] **mypy CI gate** — declared in `requirements.txt` and pre-commit
  but not in CI. Deferred per
  [ADR-0001](https://github.com/AnukritiAi-hq/anukriti-pgx-core/blob/main/docs/adr/0001-founding-engineer-scope-and-deferrals.md)
  until ruff hard-gate reaches ≥60% of codebase.

### Medium-value, research-grade improvements

**Recently shipped (session #14, 2026-05-11):**

- [x] **Method 4 — cross-ancestry extrapolation hedge.** 8th value
  `EXTRAPOLATION_WITH_CROSS_ANCESTRY_SUPPORT` on `SufficiencyDecision`,
  gated via `SufficiencyDecisionEngine(allow_cross_ancestry_extrapolation=True)`.
  Off by default, preserves byte-identical regression. 10 new tests
  (244 total). Commit `12752f1`.
- [x] **`core/simulation/` scaffold.** 3 closed enums +
  3 frozen records for cohort-scale reasoning. Commit `1441f6a`.
- [x] **Stage-1 cohort-scale demo.** `demos/cohort_demo.py` —
  deterministic 100-patient Monte Carlo across 5 super-populations
  with 16.0× SAS→AFR outcome delta. Consumes `core/simulation/` types;
  Stage-1 public-data-only constraint.

**Next candidate — Method 1 (gated on Tier 2 data arrival):**

- [ ] **Method 1 — principled cross-ancestry borrowing.** Hierarchical
  Bayesian PRS with ancestry-stratified partial pooling. Goes beyond
  M4's hedging rule to actually *learn* cross-ancestry parameters
  from the data. **Gated on Tier 2 data access** — All of Us
  Researcher Workbench or GenomeIndia FeED. Do not start until at
  least one institutional data agreement is in place; see
  [`anukriti-pgx-core/docs/research-partnerships.md`](https://github.com/AnukritiAi-hq/anukriti-pgx-core/blob/main/docs/research-partnerships.md)
  for the timeline.

**Other open items:**

- [ ] **`evidence_currency` verification check** — 7th check in the
  verification engine. Warn when cited CPIC/PMID sources are older
  than N months. Closes requirement #7 of the original 11-requirement
  safety-engine brief.
- [ ] **Adversarial benchmark suite** — `benchmarks/adversarial.py`
  with malformed planner JSON, contradictory pharmacogene results,
  missing citations. Sharpens the existing evaluation framework.
- [ ] **MCP retention policies** — TTL per collection: traces=48h,
  memory=30d, provenance+evidence=permanent.
- [ ] **Episodic memory** — `MCPEpisodicMemory` keyed on
  patient/genome hash, distinct from per-run memory. Would let us
  replay "the same patient came back a year later" scenarios.
- [ ] **Real embedding models** — replace TF-IDF mock in
  `retrieval/indexing/embeddings.py` with a proper sentence-
  embedding backend (behind the `BiomedicalRetriever` ABC).

### Longer horizon / product depth

- [ ] **Real VCF file parsing** — we currently operate on pre-resolved
  diplotypes + population codes. Upstream VCF parsing is in
  `anukriti-pgx-core`; wiring it end-to-end in swarm's demos is a
  future integration.
- [ ] **Full CPIC gene coverage in agents** — only 3 genes have
  specialist agents today (CYP2D6, CYP2C19, HLA-B). pgx-core covers
  13 genes; a new specialist agent per additional gene is a clean
  extension pattern.
- [ ] **Google ADK native agent registration** — currently we use a
  wrapper pattern (`integrations/google_adk/agents.py`). Native
  registration would shed a layer.
- [ ] **Streaming orchestrator output** — emit partial narratives as
  agents complete, rather than a single end-of-run synthesis.

### Not yet scoped

- Consensus across parallel agents that independently reason on the
  same input (multi-agent consensus algorithms).
- Agent failure recovery at runtime (we halt-and-report today; graceful
  degradation is a separate design).
- Horizontal scaling / multi-tenancy (single host + Docker Compose is
  fine until we need more).
- External security audit.

---

## Non-goals

These have not changed since the project's founding and are enforced
in code (closed enums, scope firewall, `GenerativeBoundary`):

- **Clinical decision support.** Outputs are research artifacts,
  not clinical advice.
- **Patient-facing interfaces.** The audience is researchers,
  clinicians, and trial designers — not end patients.
- **Regulatory compliance** (FDA, CE marking). If the platform ever
  moves toward clinical validation, it will be via a parallel
  validation repo with a separate lifecycle, not by retrofitting
  this one.
- **Real-time variant calling.** We consume pre-called VCF. Calling
  is a separate upstream concern (tools like DeepVariant, GATK).
- **Generic RAG chatbot.** The closed-enum
  `BiomedicalContextType` at the agent bus enforces this at
  compile-time.

---

## How to propose an addition

1. Check [`.project-status.md`](.project-status.md) — it may already
   be done and we just didn't update this roadmap.
2. Check [ADR-0001](https://github.com/AnukritiAi-hq/anukriti-pgx-core/blob/main/docs/adr/0001-founding-engineer-scope-and-deferrals.md)
   — it may be explicitly deferred with a "Revisit when" trigger.
3. Open an issue on this repo with the proposed work and a brief
   case for why it belongs here (vs. `anukriti-pgx-core` or
   `anukriti` product).
4. If accepted, it joins one of the three sections above.

---

*This roadmap evolves. The living session log at
[`.project-status.md`](.project-status.md) is the source of truth
for what has shipped. This file is the source of truth for what
we plan to ship next.*
