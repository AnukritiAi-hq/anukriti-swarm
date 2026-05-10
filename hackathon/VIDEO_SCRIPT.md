# 3-Minute Video Script — Anukriti PGx

**Total runtime: 2:55 (buffer for edit)**
**Platform:** OBS + terminal recording (primary) + quick Prompt Opinion browser flash at beginning and end.
**Voice:** calm, clinical, no rushing. Deep in the content, not performative.

---

## Frame 0 — Cold open, 0:00–0:08 (8s)

**Visual:** Prompt Opinion app homepage in browser.
**Voiceover:**
> "Healthcare AI has a last-mile problem. Prompt Opinion solved the plumbing. We built a Superpower that plugs in."

## Frame 1 — The stakes, 0:08–0:28 (20s)

**Visual:** Cut to terminal. Pre-rendered screen showing:
```
CYP2C19*2 allele frequency
  South Asian:  ████████████████████████████████████  36%
  European:     ███████████████                      15%
  African:      ██████████████████                   18%
```
**Voiceover:**
> "14% of South Asians cannot activate clopidogrel — a heart-attack drug — because they carry two copies of the CYP2C19 *star 2* variant. Today's EHRs prescribe it to them at the same rate as Europeans, where only 2% are affected. This is a published, measurable equity gap."

## Frame 2 — The hook, 0:28–0:40 (12s)

**Visual:** Terminal showing `python -m hackathon.demo` just starting. First two lines of output: "🧬 Anukriti PGx — MCP Superpower Demo" banner.
**Voiceover:**
> "Anukriti PGx is an MCP Superpower. Any A2A agent on Prompt Opinion can invoke it. FHIR in, DetectedIssue plus Provenance out. Zero domain knowledge required."

## Frame 3 — The scenario, 0:40–1:00 (20s)

**Visual:** Demo steps 1 and 2 on screen. Show Priya Patel's FHIR inputs, Asian Indian ancestry, the pending clopidogrel order.
**Voiceover:**
> "A Prompt Opinion prescriber agent sees a pending clopidogrel order for Priya Patel — 64 years old, South Asian, post-PCI. Her chart has a CYP2C19 genotype observation. The agent calls our Superpower. It reads the FHIR Patient and Observation through standard SHARP headers."

## Frame 4 — Ask first: can we answer?, 1:00–1:20 (20s)

**Visual:** Demo step 3 — sufficiency check. Show `allowsSynthesis: True`, `ruleIds: V10, sufficient, low`.
**Voiceover:**
> "Before we answer, we ask ourselves: *can we safely answer this?* Our sufficiency engine checks coverage, conflicts, uncertainty, and population bias. If any rule fails — R1 through R12, V1 through V10 — we abstain and cite the specific rule ID. Today we have enough evidence. We proceed."

## Frame 5 — The analysis, 1:20–1:45 (25s)

**Visual:** Demo step 4 — pgx_analyze_patient running, 5 specialists activating, 2ms duration. Then step 5 — the recommendation text on screen in red.
**Voiceover:**
> "Five specialists run in under 3 milliseconds. Population reasoning, graph traversal, sufficiency governance, verification, narrative synthesis. The answer: *your CYP2C19 star 2 star 2 genotype means you cannot activate clopidogrel. Recommended: prasugrel or ticagrelor instead.* The reasoning is deterministic. The narrative is generative — but bounded."

## Frame 6 — The boundary, 1:45–2:00 (15s)

**Visual:** Quick-cut to architecture screenshot or text overlay showing the four forbidden actions:
```
GenerativeBoundary forbids:
  × infer_phenotype
  × override_recommendation
  × bypass_verification
  × fabricate_claim
```
**Voiceover:**
> "Our LLM can write narrative. It cannot replace a CPIC rule, override a recommendation, bypass verification, or fabricate a claim. These four actions raise at runtime. That's how you ship AI into a clinical workflow without losing sleep."

## Frame 7 — The FHIR output, 2:00–2:25 (25s)

**Visual:** Demo steps 7 and 8 — DetectedIssue / ClinicalImpression / Provenance resource summaries, then the JSON peek.
**Voiceover:**
> "We return three FHIR R5 resources. DetectedIssue: the drug-gene risk, with severity and evidence array. ClinicalImpression: the recommendation with CPIC protocol IRIs and seven activated-agent findings. Provenance: the full audit chain. Every PMID is a real external reference. Every decision is reproducible."

## Frame 8 — The audit chain, 2:25–2:40 (15s)

**Visual:** Step 9 — the provenance agent list with the SHARP session identifier visible.
**Voiceover:**
> "Provenance carries two agents: our Superpower, and the Prompt Opinion SHARP session. Every output traces back to the original EHR session that requested it. Compliance gets what they need, day one."

## Frame 9 — Close, 2:40–2:55 (15s)

**Visual:** Prompt Opinion marketplace listing for Anukriti PGx (if published) OR terminal showing test output: `298 passed`.
**Voiceover:**
> "Anukriti PGx — now on the Prompt Opinion marketplace. Deterministic, population-aware, verified. 298 passing tests. The last mile, shipped."

---

## Production checklist

- [ ] Pre-render the 36%-15%-18% population bar graph as a still (Frame 1)
- [ ] Pre-run the demo once; record fresh take with the FastMCP stdout suppressed if noisy
- [ ] Do NOT show the FHIR token or the AWS host URL on camera
- [ ] Clock it — must be ≤ 3:00, target 2:55
- [ ] Use ffmpeg or OBS to crop the terminal tight — no OS chrome
- [ ] 16:9, 1080p, MP4 (H.264), stereo audio
- [ ] Upload to YouTube unlisted; link in Devpost submission
- [ ] Backup: upload to Google Drive as well
