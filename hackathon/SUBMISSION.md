# Devpost Submission — Anukriti PGx

> Copy-paste-ready Devpost submission fields. Tighten or relax per
> character limits; order matches the Devpost submission form.

---

## Project title

**Anukriti PGx — Pharmacogenomic Intelligence as a Superpower**

## Elevator pitch (240 chars max)

> Deterministic, population-aware pharmacogenomic reasoning as an MCP Superpower. Any healthcare agent on Prompt Opinion can invoke it: FHIR in, DetectedIssue + ClinicalImpression + Provenance out. 14% of South Asians can't activate clopidogrel — we catch it.

---

## Inspiration

In 2019, one of us watched a cardiologist prescribe clopidogrel to a
South Asian uncle post-PCI. The drug didn't work. He had another
heart event six months later. The pharmacogenomic reason — CYP2C19
*2/*2, a loss-of-function variant present in **36% of South Asians
vs 15% of Europeans** — wasn't in the EHR, wasn't in the decision
support, and wasn't in the prescriber's training. It's not an
unusual story. **14% of South Asians are CYP2C19 Poor Metabolizers
and cannot activate clopidogrel.** They're prescribed it at the same
rate as Europeans, where only 2% are affected.

We built Anukriti Swarm last year as a research platform for this
problem: 9 specialist agents, a deterministic CPIC-rule core, a
population-aware knowledge graph, and a 6-check verification engine
that blocks anything unverified.

Agents Assemble is the first hackathon where the plumbing exists —
MCP + A2A + FHIR + SHARP context propagation — for our research to
meet a real prescriber agent in a real workflow. We built the
bridge.

## What it does

**Anukriti PGx is an MCP Superpower.** Any A2A agent on Prompt
Opinion can compose it into a workflow with zero domain knowledge:

- A prescriber agent sees a pending clopidogrel order and asks:
  *"will this drug work for this patient?"*
- Our Superpower reads the patient's race (US Core extension) and
  PGx genotype (LOINC Observation) from the caller's FHIR context.
- Behind the scenes, 9 specialist agents run: population reasoning,
  pharmacogene phenotype inference, multi-strategy retrieval,
  knowledge-graph traversal, sufficiency governance, and
  deterministic verification.
- We return three cross-linked FHIR R5 resources: **DetectedIssue**
  (the drug-gene risk), **ClinicalImpression** (the recommendation
  with CPIC protocol + PMID citations), and **Provenance** (the
  full audit chain back to the Prompt Opinion SHARP session).

Five tools are exposed:

1. `pgx_analyze_patient` — end-to-end, FHIR in, FHIR out
2. `pgx_population_risk` — allele frequency + Hardy-Weinberg
   prevalence for any population
3. `pgx_retrieve_evidence` — cited CPIC/PubMed passages
4. `pgx_verify_recommendation` — 6-check verification of a
   proposed recommendation
5. `pgx_sufficiency_check` — abstention gate: *can we safely
   answer this right now?*

No hallucinations. No silent prescriptions. Every claim cites its
PMID. Every refusal names a rule ID (R1…R12, V1…V10, U1…U9).

## How we built it

**The hard architectural decision, made once and enforced in code:
a deterministic / generative boundary.** LLMs write narrative around
our outputs — they cannot replace a CPIC rule, override a
recommendation, bypass verification, or fabricate a claim. These
four actions raise at runtime. The generative boundary is a pattern
that healthcare AI desperately needs and almost nobody implements.

- **Deterministic core** — `anukriti-pgx-core==0.2.1`, a pinned
  PyPI library we published that owns 13 CPIC-curated gene tables.
  Swarm is the consumer.
- **9 specialist agents** — orchestrator, 3 population agents
  (SAS/AFR/EUR), 3 pharmacogene agents (CYP2D6/CYP2C19/HLA-B),
  evidence retrieval, verification, narrative. They communicate via
  a closed-enum typed message bus (`AgentMessageBus`), not direct
  calls.
- **Knowledge graph** — 37 nodes / 34 edges / 10 closed node kinds
  / 7 edge kinds. Every edge carries a required `ProvenanceStamp`.
  Population is a **first-class node type**, not metadata.
- **MA-RAG retrieval** — multi-strategy retrievers (population-
  aware + dense + KG traversal + diversity selector) behind an
  adaptive controller with a stopping rule.
- **Sufficiency layer** (12+10+9 deterministic rules + 3-kind
  bias detector) — every abstention cites a specific rule ID.
- **6-check verification engine** — evidence grounding,
  deterministic boundary, provenance, guideline conflicts, sparse
  population data, hallucination hooks.
- **FastMCP 3.2.4 server** with the Prompt Opinion SHARP capability
  extension (`ai.promptopinion/fhir-context`) declaring 4 FHIR
  scopes; three HTTP headers are the contract
  (`x-fhir-server-url`, `x-fhir-access-token`, `x-patient-id`).
- **FHIR R5 output** via `fhir.resources>=8.2.0` — typed
  DetectedIssue + ClinicalImpression + Provenance cross-linked
  via `fullUrl` references. Every Provenance.agent carries both
  our Superpower and the SHARP session so audit traces back to
  the original EHR user.
- **AWS deployment** — single `t3.small` EC2 instance behind a
  reverse proxy, Docker + systemd, health-check endpoint, no
  outbound writes to the FHIR server (read-only).
- **Tests** — 244 main-swarm pytest tests + 54 hackathon layer
  tests (SHARP, FHIR round-trip, MCP integration via in-memory
  transport) = 298 total, all green.

## Challenges we ran into

1. **FHIR R4 vs R5 fields.** `fhir.resources 8.2.0` is R5.
   DetectedIssue.author went from list → single Reference;
   ClinicalImpression.finding.item.concept replaced
   itemCodeableConcept. We fixed both in the adapter layer and
   added round-trip tests.

2. **Dependency conflict with `pydantic` between fastmcp 3.2.4 and
   the existing FastAPI 0.111 backend.** We kept fastmcp as an
   opt-in dependency in `hackathon/requirements.txt` so the main
   swarm's FastAPI path is unaffected.

3. **Population inference ambiguity for "Asian".** US Core race uses
   OMB codes — `2028-9` is the broad "Asian" bucket that covers both
   SAS and EAS populations. We implemented a two-pass parser: look
   for the `detailed` sub-extension first (Asian Indian, Bangladeshi,
   Pakistani, Sri Lankan, Nepalese, Bhutanese → SAS), then fall back
   to the `ombCategory` (broad Asian → EAS). This is the single most
   important ancestry distinction in our target domain.

4. **The "should we write the DetectedIssue back to FHIR?" question.**
   We chose **not to**. The caller decides whether to persist —
   we're read-only by design. Safer default, maps cleanly to
   Prompt Opinion's composition model.

## Accomplishments we're proud of

- **Zero changes to the main swarm code base.** The hackathon layer
  is strictly additive under `hackathon/`. Removing it leaves the
  main swarm byte-identical. 244 existing tests still green after
  every commit.
- **54 new tests with real SwarmRuntime execution**, not mocks.
- **Every claim cites a PMID or CPIC guideline ID.** The
  DetectedIssue we emit carries `evidence[].code.text` entries with
  `PMID:34032273`, `CPIC:CYP2C19:clopidogrel:2022`, and PharmGKB
  accession IDs. Real external references, verifiable.
- **Structured abstention.** When we cannot safely answer, we say
  so and cite a rule ID. This is rare in healthcare AI demos and
  extremely important in production.
- **Sub-30ms end-to-end latency** for the flagship SAS-clopidogrel
  case on a cold SwarmRuntime.

## What we learned

- **The real innovation in MCP for healthcare is not "tools an LLM
  can call" — it's a standardised place to propagate session
  context.** SHARP + FHIR headers solve a problem every healthcare
  AI team reinvents. Using it felt like using stdlib.
- **Deterministic-first reads well to clinicians.** We tested
  our pitch on a practicing cardiologist. The *first* thing he
  asked was "how do you know it didn't make it up?" The
  GenerativeBoundary + closed-enum ProvenanceStamp answer was
  enough. Without those, the demo would have been DOA.
- **Population context at the type level changes design pressure.**
  Once `SuperPopulation` is a closed enum, every downstream
  function *has* to handle it. That's why the sufficiency layer
  emerged so cleanly.

## What's next

- **Full CPIC gene coverage** — 10 more specialist agents
  (CYP3A4, CYP3A5, DPYD, SLCO1B1, TPMT, UGT1A1, VKORC1, and
  three HLA-B alleles beyond *15:02).
- **Real VCF ingestion** — today we accept pre-called
  diplotypes. `anukriti-pgx-core` already has a VCF caller; the
  remaining work is a new MCP tool `pgx_call_variants`.
- **Evidence currency gate** — flag CPIC/PMID sources older than
  24 months.
- **Episodic memory** — `MCPEpisodicMemory` keyed on patient hash
  so "the same patient came back a year later" replays get
  consistent reasoning.

## Built with

Python 3.12 · FastMCP 3.2.4 · fhir.resources 8.2.0 (R5) · Pydantic
2.13 · Google Gemini · OpenAI · Anthropic · HL7 FHIR R5 · CPIC
guidelines · PharmGKB · PubMed · US Core IG · MCP · A2A · SMART on
FHIR · Prompt Opinion SHARP · AWS EC2 · Docker · pytest ·
pytest-asyncio · httpx · starlette · uvicorn.

## "Try it out" links

- **Marketplace** → `https://marketplace.promptopinion.ai/superpower/anukriti-pgx`
  *(populated after publish)*
- **MCP endpoint** → `https://anukriti-pgx.{your-aws-host}/mcp`
  *(populated after AWS deploy)*
- **GitHub** → `https://github.com/AnukritiAi-hq/anukriti-swarm/tree/hackathon/agents-assemble-2026/hackathon`
- **Demo video** → `https://youtu.be/...` *(populated after recording)*
