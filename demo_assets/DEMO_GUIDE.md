# 🧬 Anukriti Swarm — Demo Guide

> For hackathon judges, presenters, and technical reviewers.

---

## What Is This?

Anukriti Swarm is a **distributed multi-agent system** that performs pharmacogenomic reasoning — determining how a patient's genetics affect their drug response.

Unlike chatbots that guess, this system:
- Uses **deterministic rules** for established science
- Grounds every claim in **cited evidence**
- Reasons about **population-specific** genetic context
- **Verifies** all outputs before delivery
- Provides **full provenance** for every conclusion

---

## The Demo Scenario

```
Patient:  South Asian ancestry
Drug:     Clopidogrel (prevents heart attacks)
Genotype: CYP2C19 *2/*2 (rs4244285)
Question: Will this drug work?
Answer:   NO — this patient cannot activate clopidogrel.
          Use prasugrel or ticagrelor instead.
```

**Why this matters:** 14% of South Asians are Poor Metabolizers for CYP2C19. They're being prescribed a drug that won't protect them from heart attacks. This is a population health equity issue.

---

## Architecture (What Runs)

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                              │
│              (decomposes query, dispatches agents)           │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  POPULATION  │ PHARMACOGENE │  RETRIEVAL   │ VERIFICATION   │
│  AGENT (SAS) │ AGENT (2C19) │  (MA-RAG)    │ (6 checks)     │
│              │              │              │                │
│  freq=36%   │  *2/*2 → PM  │  CPIC/PubMed │  confidence    │
│  common     │  high_risk   │  100% ground │  0.950         │
└──────────────┴──────────────┴──────────────┴────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   NARRATIVE AGENT   │
                    │   (3 audiences)     │
                    └─────────────────────┘
```

---

## Key Differentiators

| Feature | How We Do It |
|---------|-------------|
| No hallucinations | Deterministic CPIC rules — no LLM for core reasoning |
| Population-aware | Same gene means different things in different populations |
| Evidence-grounded | MA-RAG retrieval with citation tracking |
| Verified | 6 safety checks + TAO escalation before delivery |
| Auditable | Full provenance trail, reproducible execution |
| Fast | <2ms end-to-end, 7 stages, 5 specialist agents |

---

## Running the Demo

```bash
# Recommended: polished showcase
python -m demos.showcase

# Interactive menu with all demos
./demo_scripts/run_showcase.sh

# CLI analysis (any gene/drug/population)
python -m scripts.run_analysis --gene CYP2C19 --drug clopidogrel --population SAS --alleles "*2/*2"

# JSON output for API integration
python -m scripts.run_analysis --gene CYP2D6 --drug codeine --population EUR --alleles "*4/*4" --format json
```

---

## What Judges Should Notice

1. **The clinical scenario is real** — CYP2C19/clopidogrel is a textbook pharmacogenomics case
2. **Population context changes the interpretation** — 36% in SAS vs 15% in EUR
3. **Every output is traceable** — click any claim, find its source
4. **The system knows what it doesn't know** — sparse data warnings, confidence scores
5. **Safety-first** — verification gate prevents ungrounded claims from reaching users
6. **Modular** — add new genes, populations, or drugs without changing architecture

---

## Technical Stack

- **Python 3.11+** — type-safe, modern
- **LangGraph-compatible** — state graph execution model
- **Pydantic** — validated domain models
- **No external dependencies for core reasoning** — runs offline
- **MCP-ready** — designed for future tool server integration

---

## Available Demos

| Demo | Command | Shows |
|------|---------|-------|
| **Showcase** | `python -m demos.showcase` | Full pipeline, visually impressive |
| Population | `python -m demos.population_reasoning_demo` | Population as reasoning context |
| Pharmacogene | `python -m demos.pharmacogene_demo` | Deterministic phenotype inference |
| Retrieval | `python -m demos.retrieval_demo` | MA-RAG evidence grounding |
| Verification | `python -m demos.verification_demo` | Safety checks + escalation |
| Visualization | `python -m demos.visualization_demo` | Execution trace rendering |
| Narrative | `python -m demos.narrative_report_demo` | 3-audience report generation |
| Data | `python -m demos.biomedical_data_demo` | Biomedical data integration |
| Identity | `python -m demos.agent_identity_demo` | Agent federation overview |

---

## One-Liner Pitch

> "A swarm of specialized AI agents that collaborates to determine if your medication will work — grounded in evidence, aware of your ancestry, and verified before you see it."

---

*Built for research. Designed for impact. Ready for the future.*
