# Agent Topology

```
                    ┌───────────────────────┐
                    │    ORCHESTRATOR       │
                    │  ┌─────────────────┐  │
                    │  │ Query Router    │  │
                    │  │ Validator       │  │
                    │  │ Consensus Eng.  │  │
                    │  └─────────────────┘  │
                    └───────────┬───────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│ POPULATION AGENTS │ │ CHROMOSOME AGENTS │ │ PHARMA SPECIALIST │
├───────────────────┤ ├───────────────────┤ ├───────────────────┤
│ • Ancestry Agent  │ │ • Chr1-22 Agents  │ │ • Interaction DB  │
│ • Frequency Agent │ │ • ChrX/Y Agent    │ │ • Dosage Agent    │
│ • Stratification  │ │ • Mitochondrial   │ │ • ADR Predictor   │
│ • Ethno-PGx       │ │ • Haplotype Agent │ │ • Hypothesis Gen  │
└───────────────────┘ └───────────────────┘ └───────────────────┘
```

## Agent Communication Pattern

```
Agent A ──write──▶ Shared Memory ◀──read── Agent B
                        │
                        ▼
                   Audit Trail
```

Agents never communicate directly. All coordination happens through the shared memory layer, ensuring:
- Loose coupling between agents
- Full observability of state changes
- Deterministic replay capability
