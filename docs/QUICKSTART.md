# ⚡ Quickstart — 5 Minutes to Distributed Genomic Intelligence

---

## Prerequisites

- Python 3.11+
- Git

## Setup (1 minute)

```bash
git clone https://github.com/your-org/anukriti-swarm.git
cd anukriti-swarm
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run the Showcase (30 seconds)

```bash
python -m demos.showcase
```

You'll see:
1. Clinical scenario (South Asian patient on clopidogrel)
2. Swarm activation (5 specialist agents dispatched)
3. Population reasoning (*2 at 36% in SAS — common)
4. Pharmacogene analysis (Poor Metabolizer → high risk)
5. Evidence retrieval (PMID:34032273, 100% grounded)
6. Verification (6/6 checks PASS, confidence 0.950)
7. Critical finding: **Drug won't work. Use alternative.**

---

## Demo Flow (5 minutes)

### Step 1: The Showcase

```bash
python -m demos.showcase
```

**What to notice:** The swarm identifies that clopidogrel won't work for this patient, retrieves CPIC evidence, verifies the finding, and recommends prasugrel/ticagrelor.

### Step 2: Population Reasoning

```bash
python -m demos.population_reasoning_demo
```

**What to notice:** Same allele (CYP2D6*4) means different things in different populations. 22% in EUR (common) vs 2% in AFR (unusual).

### Step 3: Pharmacogene Agents

```bash
python -m demos.pharmacogene_demo
```

**What to notice:** Pure deterministic reasoning. No LLM. Activity scores → phenotypes → CPIC recommendations with PMIDs.

### Step 4: Verification & Safety

```bash
python -m demos.verification_demo
```

**What to notice:** Three scenarios — autonomous delivery (all pass), human escalation (ungrounded claims), multi-agent review (sparse data).

### Step 5: Full Observability

```bash
python -m demos.observability_demo
```

**What to notice:** Dashboard with metrics, telemetry spans, execution replay format.

---

## CLI Analysis (any gene/drug/population)

```bash
# Text output
python -m scripts.run_analysis --gene CYP2C19 --drug clopidogrel --population SAS --alleles "*2/*2"

# JSON output (for API integration)
python -m scripts.run_analysis --gene CYP2D6 --drug codeine --population EUR --alleles "*4/*4" --format json

# With execution trace
python -m scripts.run_analysis --gene CYP2C19 --drug clopidogrel --population AFR --alleles "*1/*2" --verbose
```

---

## Frontend (optional)

```bash
cd frontend && python -m http.server 3000
# Open http://localhost:3000/pages/index.html
```

---

## What Just Happened?

In under 2ms, the swarm:
1. **Orchestrator** decomposed the query and dispatched 5 agents
2. **Population Agent** looked up allele frequency (36% in SAS)
3. **Pharmacogene Agent** computed activity score (0.0 → Poor Metabolizer)
4. **Retrieval Agent** found 2 evidence passages (100% grounded)
5. **Verification Engine** ran 6 safety checks (all passed)
6. **Narrative Agent** generated an evidence-backed report

Every output is deterministic, traceable, and auditable.

---

## Next Steps

- Read the [Whitepaper](../whitepaper/anukriti-swarm-whitepaper.md)
- Explore [Architecture Diagrams](../architecture/diagrams/)
- Review [Ethical Considerations](research/ethical-considerations.md)
- Check the [Demo Guide](../demo_assets/DEMO_GUIDE.md) for presentations
