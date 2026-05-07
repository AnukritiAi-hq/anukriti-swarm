# Population-Aware Reasoning Flow

> "Population is reasoning context, not metadata."

## Population Reasoning Pipeline

```mermaid
flowchart TD
    INPUT[Gene + Allele + Population] --> STORE[Frequency Store<br/>PharmFreq / gnomAD]
    STORE --> FREQ[Allele Frequency<br/>e.g., CYP2C19*2 = 36% in SAS]
    FREQ --> RARITY[Rarity Classification<br/>common / low_freq / rare / very_rare]
    FREQ --> PREV[Prevalence Estimation<br/>Hardy-Weinberg → PM/IM/NM/RM/UM]
    RARITY --> RISK[Risk Context<br/>Clinical note + interpretation]
    PREV --> RISK
    STORE --> SPARSE{Sparse Data?}
    SPARSE -->|n < 500| WARN[⚠️ Sparse Data Warning]
    SPARSE -->|n ≥ 500| OK[Adequate Data]
    RISK --> OUT[Population Reasoning Result<br/>frequency + rarity + prevalence + warnings]

    style INPUT fill:#ecf0f1
    style STORE fill:#3498db,color:#fff
    style FREQ fill:#2980b9,color:#fff
    style RARITY fill:#1abc9c,color:#fff
    style PREV fill:#1abc9c,color:#fff
    style RISK fill:#16a085,color:#fff
    style WARN fill:#e74c3c,color:#fff
    style OUT fill:#27ae60,color:#fff
```

## Same Allele, Different Populations

```mermaid
graph LR
    subgraph "CYP2D6*4 Interpretation"
        direction TB
        A4[CYP2D6 *4]
        A4 --> EUR_I[EUR: 22%<br/>COMMON<br/>Expected finding]
        A4 --> SAS_I[SAS: 9%<br/>COMMON<br/>Well-characterized]
        A4 --> AFR_I[AFR: 2%<br/>LOW FREQUENCY<br/>Less common here]
        A4 --> EAS_I[EAS: 1%<br/>RARE<br/>Verify genotyping]
    end

    style EUR_I fill:#27ae60,color:#fff
    style SAS_I fill:#27ae60,color:#fff
    style AFR_I fill:#f39c12,color:#fff
    style EAS_I fill:#e74c3c,color:#fff
```

## Confidence Weighting by Sample Size

```mermaid
graph TD
    subgraph "Sample Size → Confidence"
        N10K["n ≥ 10,000<br/>Confidence: 0.95"] --> HIGH[HIGH]
        N1K["n ≥ 1,000<br/>Confidence: 0.80"] --> MOD[MODERATE]
        N100["n ≥ 100<br/>Confidence: 0.60"] --> LOW[LOW]
        NLOW["n < 100<br/>Confidence: 0.30"] --> INSUF[INSUFFICIENT]
    end

    style HIGH fill:#27ae60,color:#fff
    style MOD fill:#f39c12,color:#fff
    style LOW fill:#e67e22,color:#fff
    style INSUF fill:#e74c3c,color:#fff
```

## Population Agent Fleet

```mermaid
graph TB
    ORCH[Orchestrator] --> |population=SAS| SAS[🇮🇳 SAS Agent<br/>n=15,308<br/>CYP2C19*2: 36%]
    ORCH --> |population=AFR| AFR[🌍 AFR Agent<br/>n=20,744<br/>CYP2D6*17: 20%]
    ORCH --> |population=EUR| EUR[🇪🇺 EUR Agent<br/>n=64,603<br/>CYP2D6*4: 22%]
    ORCH -.-> |future| EAS[🇯🇵 EAS Agent]
    ORCH -.-> |future| AMR[🌎 AMR Agent]

    style SAS fill:#3498db,color:#fff
    style AFR fill:#3498db,color:#fff
    style EUR fill:#3498db,color:#fff
    style EAS fill:#bdc3c7
    style AMR fill:#bdc3c7
```
