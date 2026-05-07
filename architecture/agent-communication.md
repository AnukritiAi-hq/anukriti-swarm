# Agent Communication Model

> Defines how agents exchange information, coordinate execution, and maintain isolation.

---

## Communication Principles

1. **No direct agent-to-agent calls** — All communication flows through the shared memory layer
2. **Message-driven** — Agents produce and consume typed messages
3. **Asynchronous by default** — Agents do not block on each other
4. **Orchestrator-mediated** — The orchestrator controls message routing and ordering
5. **Immutable messages** — Once written, messages are never modified

---

## Message Architecture

```
┌──────────┐    publish     ┌──────────────────┐    subscribe    ┌──────────┐
│ Agent A  │───────────────▶│  Message Bus     │───────────────▶│ Agent B  │
└──────────┘                │  (Memory Layer)  │                └──────────┘
                            └────────┬─────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │   Audit Trail    │
                            └──────────────────┘
```

---

## Message Schema

```python
@dataclass(frozen=True)
class AgentMessage:
    message_id: str              # UUID
    source_agent: str            # Agent ID of sender
    target_agent: str | None     # None = broadcast
    message_type: MessageType    # TASK, RESULT, ERROR, SIGNAL
    payload: dict                # Typed payload per message_type
    timestamp: datetime          # UTC creation time
    correlation_id: str          # Links messages in same execution chain
    priority: int                # 0 (highest) to 9 (lowest)
```

---

## Message Types

| Type | Direction | Purpose |
|------|-----------|---------|
| `TASK_ASSIGN` | Orchestrator → Agent | Assign work to a specialist |
| `TASK_RESULT` | Agent → Orchestrator | Return execution result |
| `TASK_ERROR` | Agent → Orchestrator | Report failure |
| `EVIDENCE_REQUEST` | Agent → Retrieval Agent | Request supporting evidence |
| `EVIDENCE_RESPONSE` | Retrieval → Requesting Agent | Return evidence payload |
| `VERIFY_REQUEST` | Orchestrator → Verification Agent | Submit output for validation |
| `VERIFY_RESULT` | Verification → Orchestrator | Return validation outcome |
| `SIGNAL_ABORT` | Orchestrator → All | Cancel current execution |
| `SIGNAL_CHECKPOINT` | Orchestrator → All | Save intermediate state |

---

## Communication Patterns

### 1. Request-Response (Orchestrated)

```
Orchestrator ──TASK_ASSIGN──▶ Chromosome Agent
                                    │
Orchestrator ◀──TASK_RESULT─────────┘
```

### 2. Fan-Out / Fan-In

```
                    ┌──TASK_ASSIGN──▶ Chr1 Agent ──RESULT──┐
                    │                                       │
Orchestrator ───────┼──TASK_ASSIGN──▶ Chr2 Agent ──RESULT──┼──▶ Orchestrator
                    │                                       │     (aggregate)
                    └──TASK_ASSIGN──▶ Chr3 Agent ──RESULT──┘
```

### 3. Pipeline (Sequential)

```
Chromosome Agent ──RESULT──▶ Memory ──▶ Pharmacogene Agent ──RESULT──▶ Memory ──▶ Narrative Agent
```

### 4. Verification Gate

```
Any Agent ──RESULT──▶ Orchestrator ──VERIFY_REQUEST──▶ Verification Agent
                                                              │
                           ┌──────────────────────────────────┘
                           ▼
                    PASS → continue pipeline
                    FAIL → reject + flag for review
```

---

## Routing Rules

| Source | Target | Condition |
|--------|--------|-----------|
| Orchestrator | Population Agent | Query involves population/ancestry context |
| Orchestrator | Chromosome Agent(s) | VCF data present, route by chromosome |
| Orchestrator | Pharmacogene Agent | Drug-gene interaction query |
| Any Agent | Retrieval Agent | Evidence needed for reasoning |
| Orchestrator | Verification Agent | Any generative output produced |
| Orchestrator | Narrative Agent | All results verified, ready for synthesis |

---

## Backpressure & Flow Control

- Agents declare max concurrent tasks (default: 1)
- Orchestrator queues excess tasks
- Timeout per task type (configurable, default 30s deterministic / 120s generative)
- Dead letter queue for undeliverable messages

---

## Correlation & Tracing

Every message carries a `correlation_id` linking it to the original query. This enables:

- Full execution trace reconstruction
- Latency analysis per agent
- Debugging failed pipelines
- Audit trail completeness verification
