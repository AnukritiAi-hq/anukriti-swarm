# Data Flow Architecture

## Query Lifecycle

```
┌─────────┐    ┌────────────┐    ┌──────────────┐    ┌─────────────┐
│  Input  │───▶│  Validate  │───▶│  Classify    │───▶│  Route      │
│  Query  │    │  & Parse   │    │  (det/gen)   │    │  to Agent   │
└─────────┘    └────────────┘    └──────────────┘    └──────┬──────┘
                                                            │
                    ┌───────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                    EXECUTION LAYER                                │
├──────────────────────┬───────────────────────────────────────────┤
│  DETERMINISTIC PATH  │  GENERATIVE PATH                         │
│  ┌────────────────┐  │  ┌────────────────┐                     │
│  │ Database Query  │  │  │ LLM Inference  │                     │
│  │ Rule Engine     │  │  │ Chain-of-Thought│                     │
│  │ Validated Data  │  │  │ Hypothesis Gen │                     │
│  └────────────────┘  │  └────────────────┘                     │
└──────────────────────┴───────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                    MEMORY WRITE                                   │
│  • Result stored in vector DB                                    │
│  • State graph updated                                           │
│  • Audit entry created with provenance                           │
└──────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────┐
│                    CONSENSUS                                      │
│  • Multi-agent results aggregated                                │
│  • Confidence scoring                                            │
│  • Final response assembled                                      │
└──────────────────────────────────────────────────────────────────┘
```

## Memory Layer Detail

```
┌─────────────────────────────────────────────┐
│            SHARED MEMORY LAYER              │
├─────────────┬──────────────┬────────────────┤
│ Vector DB   │ State Graph  │ Audit Log      │
│ (Qdrant)    │ (in-memory)  │ (append-only)  │
├─────────────┼──────────────┼────────────────┤
│ Embeddings  │ Query ctx    │ Timestamps     │
│ Genomic KB  │ Agent states │ Agent ID       │
│ Papers      │ Intermediate │ Input/Output   │
│ Prior runs  │ results      │ Reasoning      │
└─────────────┴──────────────┴────────────────┘
```
