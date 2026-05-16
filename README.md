# 🧬 Anukriti Swarm

### Distributed Multi-Agent Genomic Intelligence for Population-Aware Pharmacogenomic Reasoning

> *A swarm of specialized AI agents collaborates to determine if your medication will work — grounded in evidence, aware of your ancestry, and verified before you see it.*

[![Research Only](https://img.shields.io/badge/status-research%20only-red)]()
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)]()
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green)]()
[![Agents: 9](https://img.shields.io/badge/agents-9%20specialists-purple)]()
[![CI](https://github.com/AnukritiAi-hq/anukriti-swarm/actions/workflows/ci.yml/badge.svg)](https://github.com/AnukritiAi-hq/anukriti-swarm/actions/workflows/ci.yml)
[![Tests: 234](https://img.shields.io/badge/tests-234%20passing-brightgreen)]()

---

## 🌐 Platform and docs

Anukriti Swarm is the research platform in the three-repo **Anukriti
platform** ([`anukriti-pgx-core`](https://github.com/AnukritiAi-hq/anukriti-pgx-core)
+ [`anukriti`](https://github.com/Abm32/Synthatrial) + this repo).

- 🧭 **[`PLATFORM.md`](https://github.com/AnukritiAi-hq/anukriti-pgx-core/blob/main/PLATFORM.md)**
  — canonical three-repo map, hosted in `anukriti-pgx-core`. Start here
  if you're new to the platform.
- 📚 **[`anukriti_docs`](https://github.com/AnukritiAi-hq/anukriti_docs)** —
  14-module progressive learning course covering what the platform is,
  how the pieces connect, why we chose deterministic gene matching, and
  the full tech-stack reasoning.
- 🏗️ **[`ARCHITECTURE.md`](ARCHITECTURE.md)** — what's actually built
  in this repo (not aspirational).
- 📓 **[`.project-status.md`](.project-status.md)** — living session log;
  each session #1 through #12 tells the story of one subsystem.
- 📐 **[`architecture/`](architecture/)** — per-subsystem design docs
  (unified runtime, evidence sufficiency, knowledge graph, MCP,
  verification, and more).

---

## 🎯 The Problem

**14% of South Asians cannot activate clopidogrel** (a drug that prevents heart attacks) — yet they're prescribed it at the same rate as Europeans, where only 2% are affected.[^cpic2022] The academic case is settled: European-derived polygenic risk scores lose >50% of their accuracy in non-European populations, with bias direction that is *unpredictable* even when causal variants and heritability are held constant.[^martin2017] And the gap compounds at the variant-discovery layer: ~24M SNVs and ~2.2M indels found in 2,762 LASI-DAD Indian whole-genomes are absent from gnomAD and 1000 Genomes — every PGx system that calls against those reference databases is blind to those variants.[^kerdoncuff2025]

Current pharmacogenomic systems:
- ❌ Ignore population context
- ❌ Hallucinate drug-gene interactions
- ❌ Provide no evidence trail
- ❌ Cannot be audited

## 💡 Our Solution

Anukriti Swarm decomposes pharmacogenomic reasoning into **specialized, verifiable agent tasks**:

```
Query → Orchestrator → Population Agent → Pharmacogene Agent → Evidence Retrieval → Verification → Report
         (dispatch)     (freq: 36% SAS)   (PM, high_risk)     (CPIC, PubMed)      (6/6 PASS)    (cited)
```

**Key insight:** Population is reasoning context, not metadata.

---

## ⚡ Quick Demo (30 seconds)

```bash
git clone https://github.com/your-org/anukriti-swarm.git && cd anukriti-swarm
python -m demos.showcase
```

**Output:** A South Asian patient on clopidogrel → CYP2C19 *2/*2 → Poor Metabolizer → "Use prasugrel or ticagrelor instead" (CPIC strong, PMID:34032273)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR                              │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  POPULATION  │ PHARMACOGENE │  RETRIEVAL   │ VERIFICATION   │
│  AGENTS      │ AGENTS       │  (MA-RAG)    │ (TAO)          │
├──────────────┼──────────────┼──────────────┼────────────────┤
│  SAS: 36%   │ CYP2C19: PM  │ 100% ground  │ 6/6 checks     │
│  AFR: 18%   │ CYP2D6: IM   │ PMID cited   │ conf: 0.950    │
│  EUR: 15%   │ HLA-B: risk  │ CPIC/PubMed  │ autonomous     │
└──────────────┴──────────────┴──────────────┴────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   NARRATIVE AGENT   │
                    │  Patient│Research│Audit│
                    └─────────────────────┘
```

---

## 🔬 What Makes This Different

| Feature | Traditional PGx | LLM Chatbot | **Anukriti Swarm** |
|---------|----------------|-------------|-------------------|
| Deterministic phenotyping | ✓ | ✗ | ✓ |
| Population-aware | Partial | ✗ | **✓ (first-class)** |
| Evidence-grounded | ✗ | ✗ | **✓ (100% cited)** |
| Natural language output | ✗ | ✓ | ✓ |
| Verified before delivery | N/A | ✗ | **✓ (6 checks)** |
| Full provenance | Partial | ✗ | **✓ (every claim)** |
| No hallucinations | ✓ | ✗ | **✓ (deterministic core)** |

---

## 🧪 Demo Scenarios

| Scenario | Command | Shows |
|----------|---------|-------|
| **Showcase** (recommended) | `python -m demos.showcase` | Full pipeline, visually impressive |
| Population Reasoning | `python -m demos.population_reasoning_demo` | Same allele, different populations |
| Pharmacogene Agents | `python -m demos.pharmacogene_demo` | Deterministic CPIC reasoning |
| Evidence Retrieval | `python -m demos.retrieval_demo` | MA-RAG grounding pipeline |
| Verification | `python -m demos.verification_demo` | Safety checks + escalation |
| Observability | `python -m demos.observability_demo` | Metrics, telemetry, dashboards |
| Visualization | `python -m demos.visualization_demo` | Execution trace rendering |
| Narrative Reports | `python -m demos.narrative_report_demo` | 3-audience report generation |

---

## 📊 Key Metrics

| Metric | Value |
|--------|-------|
| End-to-end latency | < 2ms |
| Verification checks | 6/6 pass |
| Evidence grounding | 100% |
| Confidence score | 0.950 |
| Agents in swarm | 9 specialists |
| Genes covered | CYP2D6, CYP2C19, HLA-B |
| Populations | SAS, AFR, EUR |

---

## 🛡️ Safety Architecture

```
Deterministic Layer (authoritative)     ← No LLM, no hallucination
─────────────────────────────────────
Verification Gate (6 checks + TAO)      ← Nothing passes unverified
─────────────────────────────────────
Generative Layer (labeled, grounded)    ← Every claim cites evidence
```

- **No hallucinations** — Core reasoning is rule-based (CPIC activity scores)
- **Every claim cited** — PMID or guideline ID on every output
- **Uncertainty surfaced** — Confidence scores, sparse data warnings
- **Escalation** — Low confidence → human review marker

---

## 🚀 Setup

```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m demos.showcase
```

See [QUICKSTART.md](docs/QUICKSTART.md) for detailed setup.

---

## 📁 Repository Structure

```
anukriti-swarm/
├── agents/           # Multi-agent framework (9 specialists)
├── population/       # Population-aware reasoning layer
├── retrieval/        # MA-RAG evidence retrieval
├── verification/     # Safety verification + TAO escalation
├── workflows/        # LangGraph-style pipeline execution
├── visualization/    # Execution trace rendering
├── narrative/        # 3-audience report generation
├── guidelines/       # CPIC guideline data
├── rules/            # Deterministic phenotype rules
├── core/             # Pydantic domain models
├── communication/    # Inter-agent messaging
├── demos/            # 12 runnable demonstrations
├── frontend/         # Research-grade web interface
├── architecture/     # Mermaid diagrams (6 diagram sets)
├── whitepaper/       # Research whitepaper
└── technical_report/ # Architecture rationale
```

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [QUICKSTART.md](docs/QUICKSTART.md) | 5-minute setup and demo |
| [INNOVATION.md](docs/INNOVATION.md) | Innovation summary for judges |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design overview |
| [Whitepaper](whitepaper/anukriti-swarm-whitepaper.md) | Research paper |
| [Technical Report](technical_report/system-design.md) | Design tradeoffs |
| [Ethics](docs/research/ethical-considerations.md) | Responsible AI |
| [Demo Guide](demo_assets/DEMO_GUIDE.md) | Presenter guide |

---

## 🌍 Why This Matters

Pharmacogenomic inequity is a global health crisis hiding in plain sight:
- **36%** of South Asians carry CYP2C19*2 (clopidogrel resistance)[^cpic2022]
- **20%** of Africans carry CYP2D6*17 (unique decreased-function allele)
- **8%** of East Asians carry HLA-B*15:02 (carbamazepine SJS/TEN risk)
- **0.28%** of Indians (enriched in the Vysya community of Andhra Pradesh / Telangana, 8 of 15 carriers) carry **BCHE L307P** — a succinylcholine-paralysis risk variant that is **absent from gnomAD entirely**. Every existing PGx system is blind to it.[^kerdoncuff2025]

These populations are underserved by current pharmacogenomic tools. Anukriti Swarm makes population context a **first-class reasoning dimension** — not an afterthought.

---

## References

The population-frequency, transferability, and variant-novelty
claims in this README are anchored in published literature. Full
PDFs and the running paper index are kept in
[`anukriti_docs/papers/`](https://github.com/AnukritiAi-hq/anukriti_docs/tree/main/papers).
The strategic synthesis of all six platform-foundational papers
and how they shape the roadmap is in
[`anukriti_docs/IDEA_REFINEMENT_AND_PHASING_2026-05-14.md`](https://github.com/AnukritiAi-hq/anukriti_docs/blob/main/IDEA_REFINEMENT_AND_PHASING_2026-05-14.md).

[^cpic2022]: Lee CR, Luzum JA, Sangkuhl K, Gammal RS, Sabatine MS,
    et al. **CPIC Guideline for CYP2C19 Genotype and Clopidogrel
    Therapy: 2022 Update.** *Clinical Pharmacology & Therapeutics*
    112(5):959–967.
    [PMID:35034351](https://pubmed.ncbi.nlm.nih.gov/35034351/);
    [NBK84114](https://www.ncbi.nlm.nih.gov/books/NBK84114/).

[^martin2017]: Martin AR, Gignoux CR, Walters RK, Wojcik GL, Neale BM,
    Gravel S, Daly MJ, Bustamante CD, Kenny EE.
    **Human Demographic History Impacts Genetic Risk Prediction
    across Diverse Populations.** *American Journal of Human
    Genetics* 100(4):635–649, April 2017.
    [doi:10.1016/j.ajhg.2017.03.004](https://doi.org/10.1016/j.ajhg.2017.03.004).

[^kerdoncuff2025]: Kerdoncuff E, Skov L, Patterson N, Moorjani P,
    Ganna A, et al. **50,000 years of evolutionary history of
    India: Impact on health and disease variation.** *Cell*
    188(13):3389–3404.e6, June 26, 2025.
    [doi:10.1016/j.cell.2025.04.027](https://doi.org/10.1016/j.cell.2025.04.027).
    LASI-DAD whole-genome cohort (n=2,762) — ~24M SNVs and
    ~2.2M indels absent from gnomAD + 1000G; six distinct Indian
    regional groupings; BCHE L307P enriched in Vysya community
    at 0.28%, invisible to gnomAD.

---

## ⚠️ Disclaimer

This is a **research system**. It is NOT intended for clinical decision-making, patient diagnosis, or drug prescribing. Always consult healthcare professionals for medical decisions.

---

## License

Apache 2.0 — See [LICENSE](LICENSE).

---

*Built for research. Designed for impact. Population-aware by design.*
