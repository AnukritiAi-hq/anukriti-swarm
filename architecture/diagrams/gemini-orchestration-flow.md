# Gemini Orchestration Flow

> Visualization of the `GeminiOrchestrator` lifecycle. Narrative walkthrough
> lives in [`architecture/gemini-orchestration.md`](../gemini-orchestration.md).

---

## 1. High-level layering

```mermaid
flowchart TD
    subgraph Facade["agents.orchestrator"]
        ORCH["GeminiOrchestrator<br/>run / compare_populations / compare_drugs"]
    end

    subgraph Framework["core.orchestrator (dependency-light)"]
        CA["ContextAssembler"]
        WP["WorkflowPlanner<br/>(Gemini + deterministic fallback)"]
        AR["AgentRouter<br/>(uses AgentRegistry)"]
        EC["ExecutionCoordinator"]
        CR["ConflictResolver"]
        GB["GenerativeBoundary<br/>(runtime safety guard)"]
        SEC["SwarmExecutionContext"]
        OT["OrchestrationTrace"]
    end

    subgraph Deterministic["workflows + agents (unchanged)"]
        PIPE["workflows.pipeline.run_pipeline<br/>7-stage deterministic"]
        PGX["Pharmacogene agents<br/>(CYP2D6, CYP2C19, HLA-B)"]
        POP["Population agents<br/>(SAS, AFR, EUR)"]
        RET["Retrieval (MA-RAG)"]
        VER["Verification engine"]
    end

    ORCH --> CA
    ORCH --> WP
    ORCH --> AR
    ORCH --> EC
    EC --> CR
    WP -.guards.-> GB
    EC -.guards.-> GB
    CA --> SEC
    WP --> SEC
    AR --> SEC
    EC --> SEC
    SEC --> OT
    EC --> PIPE
    PIPE --> PGX
    PIPE --> POP
    PIPE --> RET
    PIPE --> VER

    classDef generative fill:#fff4de,stroke:#d97706,color:#92400e;
    classDef deterministic fill:#dcfce7,stroke:#15803d,color:#14532d;
    classDef safety fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d;
    class WP,EC generative
    class PIPE,PGX,POP,RET,VER,CA,AR,CR,SEC,OT deterministic
    class GB safety
```

Colour legend:
- **green** — deterministic; same input → same output
- **orange** — uses Gemini via `AIClient` (planner and synthesis only)
- **red**    — safety / boundary enforcement

---

## 2. Single-run lifecycle (`orchestrator.run(...)`)

```mermaid
sequenceDiagram
    participant Caller
    participant GO as GeminiOrchestrator
    participant CA as ContextAssembler
    participant WP as WorkflowPlanner
    participant GB as GenerativeBoundary
    participant AR as AgentRouter
    participant EC as ExecutionCoordinator
    participant P as workflows.pipeline
    participant V as VerificationEngine (in pipeline)
    participant CR as ConflictResolver
    participant AI as AIClient (Gemini/OpenAI)

    Caller->>GO: run(gene, drug, population, alleles)
    GO->>CA: from_kwargs(...)
    CA-->>GO: SwarmExecutionContext (phase=RECEIVED)

    GO->>WP: plan(ctx)
    WP->>GB: guard_planning(ctx)
    alt boundary ok
        WP->>AI: generate(orchestration_plan prompt)
        AI-->>WP: JSON plan (or garbage)
        WP-->>WP: validate + _ensure_mandatory_steps
    else boundary trip or bad output
        WP-->>WP: deterministic fallback plan
    end
    WP-->>GO: WorkflowPlan (origin=gen|det)
    Note over WP: ctx.phase = ROUTING

    GO->>AR: route(ctx, steps)
    AR-->>AR: registry lookup per action<br/>ActivationLog per agent
    AR-->>GO: RoutingResult
    Note over AR: ctx.phase = EXECUTING

    GO->>EC: execute(ctx, routing)
    EC->>P: run_pipeline(seed_state)
    P->>V: verify(...)
    V-->>P: VerificationReport
    P-->>EC: (state, pipeline_trace)

    Note over EC: ctx.phase = VERIFYING
    EC-->>EC: aggregate verdicts (weakest wins)
    alt verification FAILED
        EC->>EC: escalate<br/>phase=ESCALATED
        EC-->>GO: CoordinationResult (no narratives)
    else PASSED / WARNING
        EC->>CR: resolve(ctx, coord_result)
        CR-->>EC: Resolution (tier)
        alt tier=BLOCK
            EC->>EC: escalate + skip synthesis
        else tier < BLOCK
            Note over EC: ctx.phase = SYNTHESIZING
            EC->>GB: guard_synthesis(ctx)
            GB-->>EC: ok
            EC->>AI: generate(orchestration_synthesis)
            AI-->>EC: audit narrative
            EC-->>EC: ctx.phase = COMPLETE
        end
        EC-->>GO: CoordinationResult
    end

    GO-->>Caller: OrchestrationResult<br/>(context, plan, routing, coord, trace)
```

---

## 3. Comparative fan-out (`compare_populations` / `compare_drugs`)

```mermaid
flowchart LR
    Q["SwarmExecutionContext<br/>populations=[SAS, AFR, EUR]"]
    FO["_fanout_rows<br/>(one seed per pop)"]
    S1["pipeline(seed_SAS)"]
    S2["pipeline(seed_AFR)"]
    S3["pipeline(seed_EUR)"]
    AGG["_propagate_verification<br/>weakest verdict wins"]
    CR["ConflictResolver<br/>tier=max across detectors"]
    CMP["_build_comparison_rows<br/>(deterministic aggregation)"]
    NAR["_synthesize<br/>audit + comparative narratives"]

    Q --> FO
    FO --> S1
    FO --> S2
    FO --> S3
    S1 --> AGG
    S2 --> AGG
    S3 --> AGG
    AGG --> CR
    CR -->|tier=BLOCK| ESC["escalate<br/>phase=ESCALATED"]
    CR -->|tier<BLOCK| CMP
    CMP --> NAR
    NAR --> DONE["phase=COMPLETE"]

    classDef fan fill:#eef2ff,stroke:#4338ca,color:#1e1b4b;
    classDef agg fill:#dcfce7,stroke:#15803d,color:#14532d;
    classDef gen fill:#fff4de,stroke:#d97706,color:#92400e;
    classDef escalate fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d;
    class S1,S2,S3 fan
    class AGG,CR,CMP agg
    class NAR gen
    class ESC escalate
```

---

## 4. Deterministic / Generative boundary

```mermaid
flowchart TB
    subgraph Allowed["Gemini MAY do"]
        A1[PLAN<br/>decompose query]
        A2[ROUTE<br/>advisory only]
        A3[EXPLAIN<br/>narrate findings]
        A4[SUMMARIZE<br/>audit summary]
        A5[COMPARE<br/>fan-out narrative]
    end

    subgraph Forbidden["Gemini MUST NOT do (raises GenerativeBoundaryViolation)"]
        B1[INFER_PHENOTYPE<br/>CPIC is authoritative]
        B2[OVERRIDE_RECOMMENDATION<br/>guidelines are fixed]
        B3[BYPASS_VERIFICATION<br/>need PASSED verdict]
        B4[FABRICATE_CLAIM<br/>must cite evidence_refs]
    end

    subgraph Guards["GenerativeBoundary guards"]
        G1[guard_planning<br/>refuse empty context]
        G2[guard_synthesis<br/>PASSED + evidence_refs]
    end

    Allowed --> Guards
    Forbidden -.blocks.-> Guards

    classDef ok fill:#dcfce7,stroke:#15803d,color:#14532d;
    classDef bad fill:#fee2e2,stroke:#b91c1c,color:#7f1d1d;
    classDef guard fill:#dbeafe,stroke:#1d4ed8,color:#1e3a8a;
    class A1,A2,A3,A4,A5 ok
    class B1,B2,B3,B4 bad
    class G1,G2 guard
```

---

## 5. Phase state machine

```mermaid
stateDiagram-v2
    [*] --> RECEIVED
    RECEIVED --> PLANNING: ContextAssembler done
    PLANNING --> ROUTING: WorkflowPlanner.plan
    ROUTING --> EXECUTING: AgentRouter.route
    EXECUTING --> VERIFYING: pipeline done
    VERIFYING --> SYNTHESIZING: verdict PASSED / WARNING + tier<BLOCK
    VERIFYING --> ESCALATED: verdict FAILED
    VERIFYING --> ESCALATED: ConflictResolver tier=BLOCK
    SYNTHESIZING --> COMPLETE: narratives produced
    SYNTHESIZING --> ESCALATED: boundary guard raises
    EXECUTING --> FAILED: all pipeline runs errored
    COMPLETE --> [*]
    ESCALATED --> [*]
    FAILED --> [*]
```
