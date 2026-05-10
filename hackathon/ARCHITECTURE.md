# Hackathon Architecture

How the `hackathon/` layer plugs into the existing Anukriti Swarm.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Prompt Opinion Platform                           │
│  ┌─────────────────┐        ┌─────────────────┐                     │
│  │ A2A prescriber  │        │ A2A cardiology  │                     │
│  │ agent           │        │ copilot         │                     │
│  └────────┬────────┘        └────────┬────────┘                     │
│           │                          │                              │
│           │      (both can compose our Superpower)                  │
│           └──────────────┬───────────┘                              │
│                          │                                           │
│                          │  MCP call  (tool + _meta + SHARP headers)│
└──────────────────────────┼──────────────────────────────────────────┘
                           │
                           │  x-fhir-server-url
                           │  x-fhir-access-token
                           │  x-patient-id
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│              hackathon/mcp_server/server.py                          │
│              POFastMCP subclass, FastMCP 3.2.4+                      │
│              Declares FHIR scopes (Patient.rs, Observation.rs,       │
│                                    MolecularSequence.rs, Condition.rs)│
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │ hackathon/sharp/context.py                                    │  │
│   │ get_sharp_context()  ──▶ FhirContext (url, token, patient)   │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│   ┌─────────────────┐   ┌─────────────────┐   ┌────────────────┐   │
│   │ analyze tool    │   │ population tool │   │ evidence tool  │   │
│   │                 │   │                 │   │                │   │
│   │ verify tool     │   │ sufficiency tool│   │                │   │
│   └────────┬────────┘   └────────┬────────┘   └────────┬───────┘   │
│            │                     │                     │           │
│            │ hackathon/fhir/input.py                   │           │
│            │ FHIR Patient + Obs/MolSeq                 │           │
│            │      → (drug, gene, population, genotype) │           │
│            ▼                     ▼                     ▼           │
└────────────┼─────────────────────┼─────────────────────┼───────────┘
             │                     │                     │
             ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    EXISTING SWARM (UNTOUCHED)                        │
│                                                                      │
│   core/runtime/SwarmRuntime           — 5-stage lifecycle            │
│       ├── orchestrator/                GeminiOrchestrator            │
│       ├── agents/ (9 specialists)      population + pharmacogene +   │
│       │                                retrieval + verification +    │
│       │                                narrative                     │
│       ├── core/verification/           4-engine safety               │
│       ├── core/evidence_sufficiency/   12+10+9 rules                 │
│       ├── knowledge_graph/             37 nodes / 34 edges           │
│       └── integrations/mcp/            6 services + persistence      │
│                                                                      │
│   Output: UnifiedExecutionReport  (frozen, 18 fields, JSON)         │
└─────────────────────────────────────────────────┬───────────────────┘
                                                  │
                                                  ▼
                             ┌─────────────────────────────────────┐
                             │ hackathon/fhir/output.py             │
                             │                                      │
                             │ Report → DetectedIssue (PM risk)    │
                             │        + ClinicalImpression          │
                             │          (with rec + PMID citations) │
                             │        + Provenance                  │
                             │          (walks the MCP chain)       │
                             └─────────────────┬───────────────────┘
                                               │
                                               ▼
                                       Response to caller
                                       (typed FHIR resources)
```

---

## Module-by-module responsibility

### `hackathon/sharp/context.py`
- Reads the 3 Prompt Opinion SHARP headers (`x-fhir-server-url`,
  `x-fhir-access-token`, `x-patient-id`).
- Returns a `SharpContext` dataclass (our rename of po-fastmcp's `FhirContext`
  to avoid confusion with the FHIR package).
- Exposes a helper `stamp_provenance(context, stamp)` that enriches our
  existing `ProvenanceStamp` with the SHARP session info.
- Raises `SharpContextMissing` when a tool that requires patient context
  is called without headers.

### `hackathon/fhir/input.py`
Accepts (in order of preference):
1. Explicit tool arguments (gene, drug, population, genotype) — supports
   the "no patient" demo case.
2. FHIR `Observation` with a genotype component (LOINC system).
3. FHIR `MolecularSequence` with `repository.readsetId`.
4. FHIR `Patient` + US Core `us-core-race` extension → super-population code.

Uses `fhir.resources>=8.2.0` typed models. Returns a
`PatientGenomicContext` dataclass ready to feed into `SwarmRuntime`.

### `hackathon/fhir/output.py`
Produces 3 FHIR R4 resources:
- `DetectedIssue` — the pharmacogenomic risk (severity, code, evidence,
  implicated medication). Severity derived from phenotype (PM → `high`).
- `ClinicalImpression` — the recommendation (findings, summary, supporting
  info, problem). Carries the CPIC guideline ID and PMID citations.
- `Provenance` — the chain (target = DetectedIssue + ClinicalImpression;
  agents = our SwarmRuntime; entity = evidence PMIDs).

All three cross-reference each other via `fullUrl` so the caller can
traverse the chain.

### `hackathon/mcp_server/server.py`
`POFastMCP` subclass declaring our FHIR scopes:
```python
fhir_scopes = [
    {"name": "patient/Patient.rs",           "required": False},
    {"name": "patient/Observation.rs",       "required": False},
    {"name": "patient/MolecularSequence.rs", "required": False},
    {"name": "patient/Condition.rs",         "required": False},
]
```
(All `required: False` so the tools degrade gracefully — you can call
them with an explicit diplotype + population even without a FHIR server.)

### `hackathon/mcp_server/tools/*.py`
Each tool:
1. Calls `get_sharp_context()` — optional for explicit-input calls.
2. If context present + patient-based call, calls `fhir/input.py` to build
   the `PatientGenomicContext`.
3. Invokes the appropriate existing swarm component:
   - `analyze` → `SwarmRuntime.run()`
   - `population` → `SASPopulationAgent / AFRPopulationAgent / ...`
   - `evidence` → `EvidenceRetriever + EvidenceSynthesizer`
   - `verify` → `VerificationEngine`
   - `sufficiency` → `ContextSufficiencyAgent`
4. Calls `fhir/output.py` to wrap the result as FHIR.
5. Returns the FHIR resource to the caller.

---

## What stays out of scope for the hackathon layer

- **No new reasoning.** We do not add a new agent, retrieval strategy, or
  rule. We expose what already exists.
- **No persistence writes.** We do NOT `POST` to the FHIR server. We only
  `read` (and optionally `search`). The caller decides whether to persist
  our `DetectedIssue`. This is a safety-by-default choice that reads well
  to judges.
- **No authentication logic.** The platform brokers the FHIR token; we
  just pass it through to `FhirClient`.
- **No UI.** `prefab_ui` apps are optional; we don't need them for the
  Superpower path.
