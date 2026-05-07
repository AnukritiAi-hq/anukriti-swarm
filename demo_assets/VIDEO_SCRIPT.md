# 🎬 Anukriti Swarm — Demo Video Script

> Duration: ~3 minutes | Audience: Hackathon judges, technical reviewers

---

## [0:00–0:20] EMOTIONAL OPENING

**Narration:**
> "Every year, millions of patients are prescribed drugs that won't work for them — not because of bad medicine, but because their genetics were never considered. For some populations, this isn't a rare edge case. It's a crisis hiding in plain sight."

**Screen:** Black background. Text fades in:
- "14% of South Asians cannot activate clopidogrel."
- "A drug prescribed to prevent heart attacks."
- Pause. Then: "Current systems don't catch this."

---

## [0:20–0:50] PROBLEM FRAMING

**Narration:**
> "Pharmacogenomics — how your genes affect your drug response — is well-understood science. CPIC guidelines exist. The data is there. But current tools have three fatal flaws."

**Screen:** Three points appear sequentially:
1. "They ignore population context" — same genotype, different meaning by ancestry
2. "LLMs hallucinate drug interactions" — fabricated recommendations
3. "No audit trail" — you can't verify why a recommendation was made

**Narration:**
> "We built Anukriti Swarm to fix this."

---

## [0:50–1:20] ARCHITECTURE INTRODUCTION

**Narration:**
> "Anukriti Swarm is a federation of specialized AI agents — each an expert in one domain — that collaborate to determine if your medication will work."

**Screen:** Architecture diagram animates in:
```
Orchestrator → Population Agent → Pharmacogene Agent → Retrieval → Verification → Report
```

**Narration:**
> "The orchestrator dispatches the query. Population agents provide ancestry-specific context. Pharmacogene agents apply deterministic CPIC rules — no LLM, no hallucination possible. The retrieval agent grounds every claim in published evidence. And the verification engine runs six safety checks before anything reaches the user."

**Screen:** Highlight each agent as mentioned. Show "DETERMINISTIC" label on pharmacogene, "VERIFIED" stamp on output.

---

## [1:20–2:10] LIVE DEMONSTRATION

**Narration:**
> "Let me show you. A South Asian patient on clopidogrel. Genotype: CYP2C19 star-two, star-two."

**Screen:** Terminal. Run:
```
python -m demos.flagship
```

**[1:30]** ACT 1 appears — allele frequency bars.

**Narration:**
> "The population agent reports: CYP2C19 star-two is at 36% in South Asians. This is common — and it means 14% of this population are Poor Metabolizers."

**[1:45]** Swarm analysis result appears.

**Narration:**
> "The pharmacogene agent computes: activity score zero. Poor Metabolizer. High risk. Clopidogrel will not work. Recommendation: use prasugrel or ticagrelor instead. Source: CPIC 2022, PMID 34032273."

**[1:55]** Verification section.

**Narration:**
> "Six verification checks. All pass. Confidence: 0.950. Escalation tier: autonomous — safe to deliver. Every claim is grounded. Every output is auditable."

**[2:05]** Conclusion section with the three statistics.

**Narration:**
> "Same drug. Different populations. Different risks. That's not a bug — that's biology. And our system understands it."

---

## [2:10–2:35] SAFETY & EXPLAINABILITY

**Narration:**
> "What makes this different from an LLM chatbot?"

**Screen:** Comparison table appears:

| | LLM Chatbot | Anukriti Swarm |
|---|---|---|
| Hallucination-free | ✗ | ✓ (deterministic core) |
| Population-aware | ✗ | ✓ (first-class) |
| Evidence-grounded | ✗ | ✓ (100% cited) |
| Verified | ✗ | ✓ (6 checks) |
| Auditable | ✗ | ✓ (full provenance) |

**Narration:**
> "Our deterministic layer makes hallucination architecturally impossible for established science. The generative layer only explains — it never decides. And nothing reaches the user without passing verification."

---

## [2:35–3:00] FUTURE VISION & CLOSE

**Narration:**
> "Today: three genes, three populations, proof of concept. Tomorrow: chromosome-level parallelism, federated genomic analysis across institutions, and MCP-integrated access to real clinical databases. The architecture is ready."

**Screen:** Future roadmap briefly flashes:
- Chromosome agents (25 parallel)
- Knowledge graph integration
- Federated multi-site analysis

**Narration:**
> "Pharmacogenomic inequity affects billions. The science exists. The data exists. What was missing was an architecture that treats population as reasoning context — not metadata. That's Anukriti Swarm."

**Screen:** Final frame:
```
🧬 Anukriti Swarm
Distributed Multi-Agent Genomic Intelligence
Built for research. Designed for impact.
```

---

## Production Notes

| Element | Recommendation |
|---------|---------------|
| Terminal font | JetBrains Mono, 14pt |
| Background | Dark (#0a0e17) |
| Recording tool | asciinema or OBS |
| Music | Subtle ambient (optional) |
| Transitions | Fade between sections |
| Pacing | Pause 1s after key statistics |

## Key Commands for Recording

```bash
# Flagship (recommended for video)
python -m demos.flagship

# Alternative: cinematic simulation (with typewriter effect)
python -m demos.swarm_simulation

# Alternative: showcase (faster, more technical)
python -m demos.showcase
```

---

*Script optimized for: emotional impact → scientific credibility → technical sophistication → memorable close.*
