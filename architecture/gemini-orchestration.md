# Gemini-powered Orchestration Layer

> A thin, Gemini-powered orchestration framework sitting on top of the
> existing deterministic Anukriti Swarm. It decomposes biomedical queries
> into specialist tasks, coordinates multi-agent workflows, and explains
> the results — **without ever making a biomedical claim itself**.

---

## 1. Why a separate orchestration layer

The deterministic pharmacogenomic pipeline (`workflows.pipeline.run_pipeline`)
already does the hard work: pharmacogene agents assign phenotypes from
CPIC activity scores, population agents look up allele frequencies,
retrieval grounds findings in literature, and verification gates every
claim before it reaches a user.

Three things were missing:

1. **Query-level coordination.** The pipeline takes a structured dict
   (`{gene, drug, population, allele1, allele2}`) and returns a state dict.
   There was no "orchestrator" that understood a *query* — natural
   language, or structured with comparative intent across populations
   or drugs — and produced a plan for how the swarm should respond.
2. **LLM-powered planning and explanation.** Gemini was being used for
   narrative generation only. There was no layer that asked Gemini
   "which specialists should handle this query?" or produced a
   synthesised, audit-ready summary of what the swarm did.
3. **A single place to enforce the deterministic/generative boundary.**
   The boundary was documented (`architecture/deterministic-generative-boundary.md`)
   and honoured by convention, but there was no runtime guard that
   refused, e.g., a Gemini prompt attempting to infer a phenotype.

The new layer fills all three.

---

## 2. Layering

```
┌────────────────────────────────────────────────────────────────────────┐
│   GeminiOrchestrator  (agents/orchestrator/gemini_orchestrator.py)     │
│   ─ high-level facade ──────────────────────────────────────────────── │
│   run(...)  compare_populations(...)  compare_drugs(...)               │
└────────────────────────────────────────────────────────────────────────┘
                                 │ uses
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│   core.orchestrator   (framework primitives, dependency-light)         │
│   ──────────────────────────────────────────────────────────────────── │
│   ContextAssembler   │  WorkflowPlanner   │  AgentRouter               │
│                      │   (Gemini + fb)     │   (AgentRegistry)         │
│                      │                     │                           │
│   ExecutionCoordinator      │   ConflictResolver   │  GenerativeBoundary│
│    (pipeline + synthesis)   │                     │                    │
│                                                                        │
│   SwarmExecutionContext   │   OrchestrationTrace                       │
└────────────────────────────────────────────────────────────────────────┘
                                 │ drives
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│   Existing deterministic swarm (unchanged)                             │
│   ──────────────────────────────────────────────────────────────────── │
│   workflows.pipeline.run_pipeline  — 7-stage deterministic pipeline    │
│   agents.*     (pharmacogene, population, retrieval, verification)     │
│   rules.*, guidelines.*, data.*, datasets.*                            │
└────────────────────────────────────────────────────────────────────────┘
```

Two ground rules for the split:

- The framework (`core.orchestrator`) never imports from the generative
  Gemini narrative layer directly. It uses the injected `AIClient` only
  for planning and synthesis, both of which are boundary-guarded.
- The deterministic swarm (`workflows.pipeline` + everything below) is
  the single source of biomedical truth. The orchestrator *invokes* it
  but does not *replace* it. Every phenotype, activity score, and
  recommendation comes from the deterministic path.

---

## 3. Component responsibilities

| Component              | File                                | Owns                                                            |
|------------------------|-------------------------------------|------------------------------------------------------------------|
| `ContextAssembler`     | `core/orchestrator/context_assembler.py` | Normalizing freeform / structured / resumed input into `SwarmExecutionContext`. |
| `WorkflowPlanner`      | `core/orchestrator/planner.py`      | Calling Gemini for plan decomposition; deterministic fallback.   |
| `AgentRouter`          | `core/orchestrator/router.py`       | Mapping planner actions onto concrete specialist agents via `AgentRegistry`. |
| `ExecutionCoordinator` | `core/orchestrator/coordinator.py`  | Running the deterministic pipeline(s), aggregating verification, synthesising narratives. |
| `ConflictResolver`     | `core/orchestrator/conflict.py`     | Cross-run conflict detection + escalation tier computation.      |
| `GenerativeBoundary`   | `core/orchestrator/boundary.py`     | Runtime enforcement of forbidden generative actions.             |
| `SwarmExecutionContext`| `core/orchestrator/context.py`      | Shared working-memory state object.                              |
| `OrchestrationTrace`   | `core/orchestrator/trace.py`        | Structured step-level observability.                             |
| `GeminiOrchestrator`   | `agents/orchestrator/gemini_orchestrator.py` | Single ergonomic entry point composing all of the above.        |

Every collaborator is constructor-injectable, so unit tests use stub
AI clients, fake pipeline runners, and widened / narrowed boundary
policies without touching the network.

---

## 4. Workflow lifecycle

A single `GeminiOrchestrator.run(...)` (and the two `compare_*` helpers
built on the same driver) goes through these phases:

```
RECEIVED
    │  ContextAssembler.from_kwargs / from_query
    ▼
PLANNING       ← Gemini decomposes query into ordered substeps
    │             (deterministic fallback if LLM unavailable or unparseable)
    ▼
ROUTING        ← AgentRouter resolves actions → concrete agents
    │             (AgentActivationLog per selected agent)
    ▼
EXECUTING      ← ExecutionCoordinator runs workflows.pipeline
    │             (one run per ctx.populations or ctx.drugs row)
    ▼
VERIFYING      ← weakest verdict across fan-out rows folded onto ctx
    │             (FAILED → escalate, WARNING/PASSED → proceed)
    ▼
(conflict resolution — cross-run divergence check)
    │             (BLOCK tier → escalate + suppress synthesis)
    ▼
SYNTHESIZING   ← audit narrative + optional comparative narrative
    │             (GenerativeBoundary.guard_synthesis before each call)
    ▼
COMPLETE       (or ESCALATED / FAILED)
```

`OrchestrationPhase` carries the current value on `SwarmExecutionContext`.
Each transition is recorded on the trace as a `StepMetric` with its
`origin` tag.

See `architecture/diagrams/gemini-orchestration-flow.md` for the
Mermaid visualization of this lifecycle.

---

## 5. The deterministic / generative boundary

`GenerativeBoundary` codifies the project's safety rules in code.
Two kinds of checks:

### 5.1 Action-level — `assert_allowed(action)`

| Allowed (generative may do)          | Disallowed (raises `GenerativeBoundaryViolation`) |
|--------------------------------------|----------------------------------------------------|
| `PLAN` — decompose into substeps      | `INFER_PHENOTYPE` — phenotype comes from CPIC       |
| `ROUTE` — advisory only               | `OVERRIDE_RECOMMENDATION` — CPIC is authoritative   |
| `EXPLAIN` — narrate verified findings | `BYPASS_VERIFICATION` — synthesis requires PASSED  |
| `SUMMARIZE` — high-level summary      | `FABRICATE_CLAIM` — every claim ⊢ evidence_refs    |
| `COMPARE` — cross-row narration       |                                                    |

### 5.2 Context-level

- `guard_planning(ctx)` — refuse to call Gemini with an empty context
  (no query and no structured fields). Prevents degenerate LLM calls.
- `guard_synthesis(ctx)` — refuse to emit user-facing output unless
  both:
  1. `ctx.verification_state` is `PASSED`, AND
  2. every pending claim is backed by at least one entry in
     `ctx.evidence_refs`.

Violations bubble up to the coordinator, which converts them into
`ESCALATED` phase transitions with a reason recorded on the trace.

The safety invariant: *no generative text reaches the caller unless
the deterministic layer produced evidence-backed, verification-passed
results for it to describe.*

---

## 6. Observability

Everything the orchestrator does is visible on the `OrchestrationTrace`:

- **`steps`** — ordered list of `StepMetric`. Every step carries an
  `origin` tag (`deterministic` | `generative`), duration, status,
  and free-form details. A reader can count how many milliseconds
  were spent in the LLM vs the deterministic layer by filtering on
  `origin`.
- **`activations`** — ordered list of `ActivationLog`. Which specialist
  agents were touched by the router, in what order, and why.
- **`reasoning_summary`** — set by the planner when Gemini produced a
  plan (the first 600 chars of its raw output) so an auditor can
  inspect what the LLM was asked for and what it returned.

The trace is designed to be JSON-serializable via `to_dict()` so it
can be stored in the MongoDB MCP trace collection and rendered by
`visualization.export` or `dashboards.cli_dashboard` without
modification.

---

## 7. Comparative runs (multi-population, multi-drug)

Both `compare_populations` and `compare_drugs` use the same fan-out
mechanism inside `ExecutionCoordinator._fanout_rows`:

- `populations` → one pipeline run per population with gene/drug fixed.
- `drugs` → one pipeline run per drug with gene/population fixed.
- Each row is a separate `workflows.pipeline.run_pipeline` invocation
  with its own correlation id (`<parent>:<population>:<drug>`).

The comparative narrative is built in two phases:

1. **Deterministic aggregation** (`_build_comparison_rows`). Flattens
   per-run results into `{label, population, drug, phenotype, risk,
   frequency, recommendation}` dicts. No LLM call.
2. **Generative narration** (`_synthesize`). The comparative rows are
   injected into the `orchestration_comparative` prompt so Gemini
   explains *why* the rows differ — without seeing any input it
   could invent from.

---

## 8. Conflict resolution and escalation

Cross-run conflicts in a fan-out are detected by `ConflictResolver`
between verification and synthesis:

| Kind                         | Tier       | Meaning                                           |
|------------------------------|------------|---------------------------------------------------|
| `verification_divergence`    | `REVIEW`   | Verdicts differ across rows.                      |
| `recommendation_divergence`  | `ADVISORY` | Recs differ (expected; narrative should emphasize). |
| `evidence_gap` (partial)     | `REVIEW`   | Some rows lack citations.                         |
| `evidence_gap` (total)       | `BLOCK`    | Every row lacks citations; synthesis suppressed.  |

Tiers compose as a simple max (`NONE < ADVISORY < REVIEW < BLOCK`).
The coordinator honours them:

- `NONE` / `ADVISORY` / `REVIEW` — synthesis proceeds; the narrative
  surfaces the conflict to the reader.
- `BLOCK` — phase transitions to `ESCALATED`, synthesis is skipped,
  deterministic results remain accessible to the caller.

Escalation also happens (independently of the resolver) when:

- Pipeline execution fails on every fan-out row.
- Aggregate verification verdict is `FAILED`.
- `GenerativeBoundary.guard_synthesis` raises (malformed context).

All escalations write a step with status `error` and `reason` on the
trace.

---

## 9. Test surface

Every primitive in `core.orchestrator` is constructor-injectable.
The test strategy used during development:

- **`ContextAssembler`** — pure function; five input shapes covered
  (structured kwargs, freeform, hints override, resume, synthesized
  query).
- **`GenerativeBoundary`** — every forbidden action asserted, both
  context-level guards asserted.
- **`WorkflowPlanner`** — stub `AIClient` covers fallback,
  generative-ok, malformed-LLM, partial-LLM (injection path),
  comparative injection, and empty-context boundary trip.
- **`AgentRouter`** — single-pop, multi-pop fan-out, coordinator-owned
  actions, unknown gene error path.
- **`ExecutionCoordinator`** — fake pipeline runner covers single-run,
  comparative fan-out, verification failure → escalation, evidence
  gap → BLOCK.
- **`GeminiOrchestrator`** — end-to-end smoke with real pipeline + stub
  AI, all three public entry points.

The demo (`demos.gemini_orchestrator_demo`) also exercises the whole
stack against the real `workflows.pipeline`.

---

## 10. Backward compatibility

The refactor converted `agents/orchestrator.py` into
`agents/orchestrator/` — a package. The original `OrchestratorAgent`
lives in `agents/orchestrator/agent.py` and is re-exported from the
package `__init__.py`, so every existing import site keeps working:

```python
from agents.orchestrator import OrchestratorAgent
from agents import OrchestratorAgent
```

The new `GeminiOrchestrator` is a separate concept that lives next to
it; nothing else had to change. The 18 pre-existing demos all still
pass after the refactor, verified by running them in sequence.

---

## 11. What this layer is **not**

- Not a replacement for the LangGraph pipeline (`workflows/pipeline.py`).
  It wraps it.
- Not a Google ADK dependency. `GeminiOrchestrator` is pure-Python; the
  existing `integrations/google_adk.ADKOrchestrator` is a separate,
  ADK-specific specialization that predates this layer.
- Not a verification engine. Verification still happens inside the
  deterministic pipeline (`verification.engine`); the orchestrator
  only reads and aggregates verdicts.
- Not a replacement for the deterministic/generative boundary doc. It
  implements the rules the doc already describes.
