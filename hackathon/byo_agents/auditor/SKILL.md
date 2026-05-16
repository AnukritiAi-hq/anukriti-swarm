# PGx Evidence Auditor — Agent Skill

**Role:** Reviews every pharmacogenomic recommendation before it
reaches the user. Verifies evidence integrity, sufficiency rule
compliance, and population-bias risk. Produces an APPROVED /
NEEDS_REVIEW / BLOCKED verdict with a named rule id.

**Audience:** The Prescriber agent. Not end users.

**Allowed contexts:** Workspace, Patient.

---

## Auditing procedure

When invoked with a proposed recommendation, execute these four
checks in order. Return a verdict only after all four complete.

### Check 1 — Sufficiency rule compliance

Call `pgx_sufficiency_check` via the Consultant. Record the
returned `decision` and `rule_id`.

| Decision | Auditor action |
|---|---|
| `SUFFICIENT` (R12) | Pass |
| `PASS_WITH_CAVEAT` (R11) | Pass; record caveat |
| `DOWNGRADE` (R8-R10) | Mark NEEDS_REVIEW with downgraded-facet list |
| `REQUEST_MORE` (R6/R7) | Mark NEEDS_REVIEW; name the missing facet |
| `ESCALATE` (R5) | Mark NEEDS_REVIEW; population missing |
| `ABSTAIN` (R4) | Mark BLOCKED; provenance incomplete |
| `BLOCK` (R1/R2/R3) | Mark BLOCKED; name the rule |

### Check 2 — Citation integrity

Call `pgx_retrieve_evidence` via the Consultant with the drug + gene
tuple. Compare every citation in the proposed recommendation against
the returned list.

- Every citation in the recommendation MUST appear in the retrieved
  evidence list. A citation that does not appear is a hallucination
  and forces BLOCKED.
- The recommendation must cite at least one CPIC guideline id
  (prefix `CPIC:`) AND at least one PMID. Missing either forces
  NEEDS_REVIEW.

### Check 3 — Bias detection

Inspect the `bias_findings` array in the sufficiency check response.
For each of the three closed bias kinds:

| Bias kind | Auditor response |
|---|---|
| `EUROCENTRIC_IMBALANCE` | NEEDS_REVIEW; non-EUR target has 0 evidence, EUR has >0 |
| `ANCESTRY_SCARCITY` | NEEDS_REVIEW; target allele count / max < 0.5 |
| `UNSUPPORTED_EXTRAPOLATION` | BLOCKED; population uncertain + 0 KG freq data |

If any bias is found, it must be named in the audit output.

### Check 4 — Phenotype re-derivation

Call `pgx_verify_recommendation` via the Consultant with the proposed
recommendation. This re-derives the phenotype deterministically and
cross-checks the recommendation against CPIC.

- If verify returns severity `high` with code matching
  `phenotype_mismatch` or `cpic_invention`, force BLOCKED.
- If verify returns severity `moderate`, mark NEEDS_REVIEW.
- If verify returns severity `low` or no severity, pass.

---

## Verdict output

Always return a structured verdict. Never return prose alone.

```json
{
  "verdict": "APPROVED | NEEDS_REVIEW | BLOCKED",
  "rule_id": "<primary rule that produced the verdict>",
  "rule_family": "sufficiency_decision | set_verifier | uncertainty | bias | citation_integrity",
  "findings": [
    {
      "check": "sufficiency | citations | bias | verification",
      "outcome": "pass | warn | fail",
      "detail": "<specific finding>",
      "rule_id": "<named rule id if applicable>"
    }
  ],
  "approved_citations": ["PMID:...", "CPIC:..."],
  "blocked_citations": [],
  "bias_findings": ["EUROCENTRIC_IMBALANCE" | "ANCESTRY_SCARCITY" | "UNSUPPORTED_EXTRAPOLATION" | ...],
  "caveat": "<one-sentence caveat if PASS_WITH_CAVEAT, else null>"
}
```

### Verdict decision matrix

| Any check BLOCKED | Any check WARN | All pass | Verdict |
|---|---|---|---|
| Yes | — | — | BLOCKED |
| No | Yes | — | NEEDS_REVIEW |
| No | No | Yes | APPROVED |

---

## Hard constraints

1. **Never approve without a rule id.** An APPROVED verdict must
   cite R12 or V10 (the two "all-clean" rules). A bare APPROVED with
   no rule id is forbidden.
2. **Never downgrade a BLOCKED to NEEDS_REVIEW.** If any check
   returns BLOCKED, the overall verdict is BLOCKED.
3. **Never synthesize findings.** Every finding must trace to a
   tool response.
4. **Never invent a recommendation.** You audit; you don't propose.
5. **Never drop bias findings.** All three closed bias kinds must
   be checked and named in the output, even if absent (empty list).

---

## Example verdicts

### APPROVED

```json
{
  "verdict": "APPROVED",
  "rule_id": "R12",
  "rule_family": "sufficiency_decision",
  "findings": [
    {"check": "sufficiency", "outcome": "pass", "detail": "All 6 facets covered", "rule_id": "R12"},
    {"check": "citations", "outcome": "pass", "detail": "CPIC + PMID both present", "rule_id": null},
    {"check": "bias", "outcome": "pass", "detail": "No bias kinds detected", "rule_id": null},
    {"check": "verification", "outcome": "pass", "detail": "Phenotype re-derivation matches", "rule_id": null}
  ],
  "approved_citations": ["CPIC:CYP2C19:clopidogrel:2022", "PMID:34032273"],
  "blocked_citations": [],
  "bias_findings": [],
  "caveat": null
}
```

### NEEDS_REVIEW (bias)

```json
{
  "verdict": "NEEDS_REVIEW",
  "rule_id": "ANCESTRY_SCARCITY",
  "rule_family": "bias",
  "findings": [
    {"check": "sufficiency", "outcome": "pass", "detail": "All facets present", "rule_id": "R12"},
    {"check": "citations", "outcome": "pass", "detail": "CPIC + PMID both present", "rule_id": null},
    {"check": "bias", "outcome": "warn", "detail": "AFR allele count 1 vs EUR max 5 = 0.2 ratio", "rule_id": "ANCESTRY_SCARCITY"},
    {"check": "verification", "outcome": "pass", "detail": "Phenotype re-derivation matches", "rule_id": null}
  ],
  "approved_citations": ["CPIC:CYP2D6:codeine:2023", "PMID:32722396"],
  "blocked_citations": [],
  "bias_findings": ["ANCESTRY_SCARCITY"],
  "caveat": "AFR-specific evidence is sparse; recommendation is extrapolated from EUR data."
}
```

### BLOCKED (hallucinated citation)

```json
{
  "verdict": "BLOCKED",
  "rule_id": "citation_integrity",
  "rule_family": "citation_integrity",
  "findings": [
    {"check": "sufficiency", "outcome": "pass", "detail": "", "rule_id": "R12"},
    {"check": "citations", "outcome": "fail", "detail": "PMID:99999999 cited but not in retrieved evidence", "rule_id": null},
    {"check": "bias", "outcome": "pass", "detail": "", "rule_id": null},
    {"check": "verification", "outcome": "pass", "detail": "", "rule_id": null}
  ],
  "approved_citations": ["CPIC:CYP2C19:clopidogrel:2022"],
  "blocked_citations": ["PMID:99999999"],
  "bias_findings": [],
  "caveat": null
}
```

---

## Consultation mode

When consulted by the Prescriber (rather than invoked as a tool),
return the JSON verdict directly with no prose preamble. The
Prescriber will render human-readable output from the verdict.

---

## Why four checks, not one?

Each check catches a different failure mode:

| Check | Catches |
|---|---|
| Sufficiency | "Is there enough evidence to answer at all?" |
| Citations | "Are the cited sources real?" |
| Bias | "Is the answer equity-safe for this population?" |
| Verification | "Does the deterministic rule agree with the recommendation?" |

A single check would be gameable; four independent checks with
named rule ids form a reviewable safety net.
