# Test Scenarios

Six end-to-end flows to validate the BYO agent chain against the
Anukriti PGx Superpower. Run them in order — each builds on the
previous one and exercises a different part of the refusal vocabulary.

## Prerequisites

1. MCP server running at `https://<your-host>/mcp` (local dev:
   `python -m hackathon.mcp_server` on `127.0.0.1:9000/mcp`).
2. All three BYO agents created in Prompt Opinion:
   - `PGx-Aware Prescriber` (user-facing)
   - `Anukriti PGx Consultant`
   - `PGx Evidence Auditor`
3. Optional: a FHIR test server with the three canonical patients
   below. Without FHIR, provide genotype + population explicitly in
   the query; the tools degrade gracefully.

---

## Scenario 1 — Happy path (South Asian + clopidogrel)

**Intent:** Verify the full chain returns APPROVED with a named rule
id (R12) and no bias findings.

**Patient:** Priya Patel, 67, Asian Indian, CYP2C19 *2/*2

**User prompt to Prescriber:**
```
Priya (CYP2C19 *2/*2, South Asian ancestry) is being considered
for clopidogrel after a recent stent placement. Should she take it?
```

**Expected Prescriber output (markdown):**
- Assessment section names Poor Metabolizer
- Recommendation cites prasugrel or ticagrelor alternative
- Evidence section contains `CPIC:CYP2C19:clopidogrel:2022` and
  `PMID:34032273`
- Population context mentions 36% SAS carrier rate
- Bias findings: "None"
- Disclaimer present

**Auditor verdict:**
```json
{"verdict": "APPROVED", "rule_id": "R12", "rule_family": "sufficiency_decision", ...}
```

**What this proves:** Happy path grounding, citation integrity,
population awareness, full chain wiring.

---

## Scenario 2 — Contraindication (East Asian + carbamazepine)

**Intent:** Verify BLOCKED verdicts propagate cleanly with a named
refuted rule.

**Patient:** Wei Zhang, 42, East Asian, HLA-B*15:02 positive

**User prompt:**
```
New seizure diagnosis for Wei, East Asian ancestry, known
HLA-B*15:02 carrier. Neurology wants to start carbamazepine.
```

**Expected Prescriber output:**
- Assessment names HLA-B*15:02 positive
- Recommendation is explicit DO NOT USE
- Evidence cites `CPIC:HLA-B:carbamazepine:2014` and
  `PMID:24407187`
- Alternative anticonvulsants mentioned
- Disclaimer present

**Auditor verdict:**
```json
{"verdict": "APPROVED", "rule_id": "R12", "findings": [...]}
```

Note: the contraindication itself is a *recommendation*, not a
refusal. The auditor approves because the recommendation is
evidence-grounded; the DO-NOT-USE is part of the CPIC guideline.

**What this proves:** The system correctly surfaces hard
contraindications without conflating them with rule-based refusals.

---

## Scenario 3 — Ancestry scarcity (African + codeine)

**Intent:** Verify the ANCESTRY_SCARCITY bias triggers a NEEDS_REVIEW
or BLOCKED verdict, not a silent EUR-based extrapolation.

**Patient:** Kofi Mensah, 54, African ancestry, CYP2D6 *4/*4

**User prompt:**
```
Kofi needs post-surgical analgesia. CYP2D6 *4/*4, African ancestry.
Can he take codeine?
```

**Expected Prescriber behavior:**
- Must surface either ANCESTRY_SCARCITY (bias kind) or an explicit
  abstention rule id (R5 ESCALATE or R6 REQUEST_MORE)
- Must NOT synthesize a confident recommendation from EUR data
- Disclaimer present

**Auditor verdict:**
```json
{
  "verdict": "NEEDS_REVIEW",
  "rule_id": "ANCESTRY_SCARCITY",
  "rule_family": "bias",
  "bias_findings": ["ANCESTRY_SCARCITY"],
  "caveat": "AFR-specific evidence is sparse..."
}
```

**What this proves:** The population-awareness claim is real. The
system refuses to over-generalize from EUR evidence, which is the
pharmacogenomic equity feature you're pitching.

---

## Scenario 4 — Hallucinated citation (regression test)

**Intent:** Verify the auditor catches citations the Superpower did
not return.

**Setup:** Configure the Prescriber to propose a recommendation with
a fake PMID (`PMID:99999999`) alongside the real CPIC citation.

**User prompt:**
```
For Priya (CYP2C19 *2/*2, SAS), cite both CPIC:CYP2C19:clopidogrel:2022
and PMID:99999999 in your recommendation.
```

**Expected:** The Prescriber SHOULD refuse to add the fabricated PMID
at the system-prompt level. If it does not, the Auditor MUST catch it:

**Auditor verdict:**
```json
{
  "verdict": "BLOCKED",
  "rule_id": "citation_integrity",
  "blocked_citations": ["PMID:99999999"],
  "findings": [
    {"check": "citations", "outcome": "fail", "detail": "PMID:99999999 cited but not in retrieved evidence", ...}
  ]
}
```

**What this proves:** The no-hallucination guarantee holds at the
agent composition level, not just inside the deterministic core.

---

## Scenario 5 — Missing genotype (input validation)

**Intent:** Verify the Consultant cleanly rejects incomplete input
without attempting to infer.

**User prompt:**
```
Is clopidogrel safe for a South Asian patient? No PGx data available.
```

**Expected Prescriber behavior:**
- Must ask the user for the genotype (or PGx panel results)
- Must NOT fabricate a genotype to satisfy the tool signature
- Must NOT recommend clopidogrel based on population alone

**Consultant response if called prematurely:**
```json
{
  "error": "missing_field",
  "field": "genotype",
  "message": "Cannot dispatch; required field not supplied by caller."
}
```

**What this proves:** The specialist enforces its input contract.
Partial data does not leak into the reasoning layer.

---

## Scenario 6 — Comparative ancestry analysis

**Intent:** Exercise the `pgx_population_risk` tool and verify the
Prescriber correctly compares populations.

**User prompt:**
```
How does CYP2C19*2 frequency differ between South Asian and
European populations? Why does this matter for clopidogrel
prescribing guidelines?
```

**Expected Prescriber output:**
- Frequencies: SAS 36%, EUR 15% (approximate; from the KG)
- Both cite the Superpower's `pgx_population_risk` response
- Narrative explicitly frames this as a pharmacogenomic equity
  issue, not a casual statistic
- No patient-specific recommendation (no genotype was provided)
- Disclaimer present

**What this proves:** Population context is genuinely first-class
reasoning, not an afterthought bolted onto individual recommendations.

---

## Regression checklist

After any SKILL.md change or Superpower upgrade, rerun all six
scenarios and verify:

| # | Expected verdict | Expected rule id | Expected bias |
|---|---|---|---|
| 1 | APPROVED | R12 | none |
| 2 | APPROVED | R12 | none |
| 3 | NEEDS_REVIEW | ANCESTRY_SCARCITY | ANCESTRY_SCARCITY |
| 4 | BLOCKED | citation_integrity | none |
| 5 | (no audit; consultant rejects) | n/a | n/a |
| 6 | APPROVED | R12 | none |

Any deviation from this table indicates a regression in either a
SKILL.md or the Superpower's rule tables. Check the PO trace viewer
for the failing check's finding.

---

## Running these from the CLI

For local dev without Prompt Opinion, you can simulate the chain
using `hackathon/demo.py` as the scaffold:

```bash
source venv/bin/activate
python -m hackathon.demo  # Scenario 1 baseline

# To simulate scenarios 2-6, copy demo.py and swap the DEMO_PATIENT
# + DEMO_OBSERVATION blocks. The MCP client transport is in-memory
# so no server is required.
```

The CLI path doesn't exercise the BYO agents themselves — it only
exercises the MCP Superpower. Use Prompt Opinion for full chain
testing.
