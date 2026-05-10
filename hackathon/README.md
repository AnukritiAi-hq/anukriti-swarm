# Anukriti PGx — Agents Assemble 2026 Submission

> **Pharmacogenomic Intelligence as a Superpower.**
> Deterministic, population-aware drug-response reasoning that any healthcare
> agent can invoke. Built on MCP + SHARP + FHIR.

---

## The 30-second pitch

When a prescribing agent reaches for clopidogrel, it should ask one question
first: **"Will this drug actually work for this patient?"** For 14% of South
Asians, the answer is *no* — they cannot activate clopidogrel because of
CYP2C19*2 homozygosity. Today's EHRs prescribe it anyway.

**Anukriti PGx** is an MCP Superpower that answers that question in a way
traditional PGx tools and LLM chatbots cannot:

- **Deterministic** — no LLM hallucinations in the clinical reasoning core
- **Population-aware** — ancestry is a first-class reasoning dimension, not metadata
- **Evidence-grounded** — every claim cites a CPIC guideline or PubMed PMID
- **Verified** — 6 safety checks before any output reaches the calling agent
- **FHIR-native** — inputs and outputs are standard HL7 FHIR resources

Any A2A agent on Prompt Opinion can compose our Superpower into its workflow
without knowing a single thing about pharmacogenomics.

---

## What we ship (as an MCP Superpower)

A FastMCP server (`po-fastmcp` compatible) exposing 5 tools over the standard
Prompt Opinion FHIR context:

| Tool | Returns | FHIR output |
|---|---|---|
| `pgx_analyze_patient` | Phenotype + CPIC recommendation for drug/gene tuple | `DetectedIssue` + `ClinicalImpression` |
| `pgx_population_risk` | Allele frequency + prevalence in this patient's population | Structured JSON |
| `pgx_retrieve_evidence` | Cited CPIC/PubMed passages | Structured JSON with PMIDs |
| `pgx_verify_recommendation` | 6-check verification of a proposed recommendation | `DetectedIssue` (severity-stamped) |
| `pgx_sufficiency_check` | "Do we have enough evidence to answer this safely?" | Structured JSON with rule IDs |

Every tool call:
1. Reads SHARP headers (`x-fhir-server-url`, `x-fhir-access-token`, `x-patient-id`)
2. Pulls the patient's race/ethnicity + PGx genotype from the FHIR server
3. Runs the existing `SwarmRuntime` (9 specialist agents, deterministic core)
4. Writes a `Provenance` chain back to the FHIR server (if scope allows)
5. Returns a typed FHIR resource the caller can consume

---

## Why this wins on the judging axes

| Criterion | Our story |
|---|---|
| **AI Factor** | Gemini orchestrates + narrates; deterministic rule tables decide. LLM cannot override a CPIC recommendation — it's blocked at the `GenerativeBoundary`. This is exactly where LLMs belong in clinical AI. |
| **Potential Impact** | 14% of South Asians can't activate clopidogrel (CYP2C19*2/*2). 8% of East Asians risk SJS/TEN on carbamazepine (HLA-B*15:02). 20% of Africans carry CYP2D6*17. Current EHRs ignore ancestry. This is a published, measurable health equity gap. |
| **Feasibility** | Research-grade positioning (`DetectedIssue` + `Provenance`, never a direct prescription). Deterministic-first. Every claim cited. Full provenance chain. Closed-enum scope firewalls. CPIC is already in production at Vanderbilt, Mayo, St. Jude — the substrate is clinically validated. |

---

## Layout of this folder

```
hackathon/
├── README.md                 <-- this file
├── SUBMISSION.md             Devpost submission copy (inspiration / what / how / challenges)
├── VIDEO_SCRIPT.md           3-minute beat-by-beat script for the demo video
├── PLAN.md                   Session plan with time budget + milestones
├── ARCHITECTURE.md           How this layer integrates with the main swarm
│
├── mcp_server/
│   ├── server.py             FastMCP entry point (PoFastMCP subclass with FHIR scopes)
│   ├── tools/
│   │   ├── analyze.py        pgx_analyze_patient
│   │   ├── population.py     pgx_population_risk
│   │   ├── evidence.py       pgx_retrieve_evidence
│   │   ├── verify.py         pgx_verify_recommendation
│   │   └── sufficiency.py    pgx_sufficiency_check
│   └── __init__.py
│
├── sharp/
│   └── context.py            SHARP context adapter (FHIR headers -> SwarmRuntime context)
│
├── fhir/
│   ├── input.py              FHIR Patient/Observation/MolecularSequence -> (drug, gene, population, genotype)
│   └── output.py             SwarmRuntime result -> FHIR DetectedIssue + ClinicalImpression + Provenance
│
├── tests/
│   ├── test_mcp_server.py    Integration tests (spawn server, invoke tools via MCP client)
│   ├── test_sharp.py         SHARP context parsing
│   └── test_fhir.py          FHIR adapter round-trips
│
├── demo.py                   End-to-end demo for the 3-min video
└── requirements.txt          Hackathon-local deps (fastmcp + fhir.resources)
```

---

## Running locally

```bash
# From the repo root
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install -r hackathon/requirements.txt

# Start the MCP server
python -m hackathon.mcp_server.server

# Server listens on http://127.0.0.1:9000/mcp
# Point Prompt Opinion or any MCP client at that URL.

# Run the end-to-end demo (no platform needed)
python -m hackathon.demo

# Run the test suite
pytest hackathon/tests/ -v
```

---

## Disclaimer

This is a **research system**. Outputs are `DetectedIssue` resources for
clinician review — never direct prescriptions. See the main repo
[`README.md`](../README.md) and [`docs/safety.md`](../docs/safety.md) for the
full safety architecture.
