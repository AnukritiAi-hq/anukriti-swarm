# Prompt Opinion Form — Fill-In Cheat Sheet

One-page reference for filling the PO BYO agent form. For each of the
three agents, this maps every form field to the exact value to paste.

## Legend

- ✅ = check the box
- ☐ = leave unchecked
- *(blank)* = leave the field empty
- `→ FILE` = paste the contents of the referenced file

---

## Agent 1 — PGx-Aware Prescriber

| Form field | Value |
|---|---|
| Allowed Contexts — Workspace | ✅ |
| Allowed Contexts — Patient | ✅ |
| Allowed Contexts — Group | ☐ |
| Agent Name | `PGx-Aware Prescriber` |
| Description | `Clinical reasoning agent that evaluates medication choices through a pharmacogenomic lens. Consults the Anukriti PGx Superpower before finalizing any prescribing recommendation. Research-grade; never issues direct prescriptions.` |
| Timeout Seconds | `90` |
| Po Chat Selectable | ✅ |
| Default Agent | ☐ |
| Publish to the Marketplace | ☐ *(flip to ✅ after end-to-end testing)* |
| System Prompt | `→ prescriber/SKILL.md` (paste entire file contents) |
| Consultation Prompt | *(blank — this agent is user-facing, not consulted)* |
| JSON Response Format | *(blank — Prescriber returns markdown)* |
| Document Sources | *(none)* |
| Agent Skills | `→ prescriber/SKILL.md` |
| Guardrails | Enable any "no direct medical advice" / "require citations" guardrails PO offers |

**MCP Server binding:** Attach the Anukriti PGx Superpower so this
agent can consult tools indirectly via the Consultant.

**Agents to consult:** `Anukriti PGx Consultant`, `PGx Evidence Auditor`

---

## Agent 2 — Anukriti PGx Consultant

| Form field | Value |
|---|---|
| Allowed Contexts — Workspace | ☐ |
| Allowed Contexts — Patient | ✅ |
| Allowed Contexts — Group | ☐ |
| Agent Name | `Anukriti PGx Consultant` |
| Description | `Specialist agent that consults the Anukriti PGx MCP Superpower for population-aware pharmacogenomic reasoning. Deterministic-first; every claim cited. Returns structured FHIR DetectedIssue resources.` |
| Timeout Seconds | `60` |
| Po Chat Selectable | ☐ |
| Default Agent | ☐ |
| Publish to the Marketplace | ✅ *(this is the shareable specialist)* |
| System Prompt | `→ consultant/SKILL.md` |
| Consultation Prompt | `→ consultant/SKILL.md` *(same file; consultation contract is identical to tool contract)* |
| JSON Response Format | `→ RESPONSE_SCHEMAS.md` **PGx Consultant** block |
| Document Sources | *(none)* |
| Agent Skills | `→ consultant/SKILL.md` |
| Guardrails | Enable "cite sources" / "no hallucination" guardrails if available |

**MCP Server binding:** Attach the Anukriti PGx Superpower. This agent
is the ONLY one that directly invokes the 5 MCP tools.

**Agents to consult:** none

---

## Agent 3 — PGx Evidence Auditor

| Form field | Value |
|---|---|
| Allowed Contexts — Workspace | ✅ |
| Allowed Contexts — Patient | ✅ |
| Allowed Contexts — Group | ☐ |
| Agent Name | `PGx Evidence Auditor` |
| Description | `Audits pharmacogenomic recommendations for evidence sufficiency, citation integrity, and population-bias risk. Runs before any recommendation reaches the clinician.` |
| Timeout Seconds | `45` |
| Po Chat Selectable | ☐ |
| Default Agent | ☐ |
| Publish to the Marketplace | ☐ |
| System Prompt | `→ auditor/SKILL.md` |
| Consultation Prompt | `→ auditor/SKILL.md` |
| JSON Response Format | `→ RESPONSE_SCHEMAS.md` **Evidence Auditor** block |
| Document Sources | *(none)* |
| Agent Skills | `→ auditor/SKILL.md` |
| Guardrails | Enable "require structured output" if available |

**MCP Server binding:** Attach the Anukriti PGx Superpower (the
Auditor calls sufficiency + evidence tools via the Consultant, but
direct binding is a useful fallback).

**Agents to consult:** `Anukriti PGx Consultant`

---

## Setup order

Create the agents in this order so dependencies resolve:

1. **PGx Evidence Auditor** (depends on Consultant)
2. **Anukriti PGx Consultant** (no dependencies — create first if
   PO requires dependency-free creation)
3. **PGx-Aware Prescriber** (depends on both)

In practice, PO usually tolerates out-of-order creation as long as
you bind the "Agents to consult" after all three exist.

---

## Post-creation checklist

- [ ] MCP server URL added to PO workspace: `https://<host>/mcp`
- [ ] Superpower detected with 5 tools + SHARP capability extension
- [ ] All 3 agents created with the fields above
- [ ] Consultation links wired (Prescriber → Consultant + Auditor,
      Auditor → Consultant)
- [ ] Run all 6 scenarios from `TEST_SCENARIOS.md`
- [ ] Regression table matches (APPROVED/R12, BLOCKED/
      citation_integrity, etc.)
- [ ] Only after all green: flip `Publish to Marketplace` on the
      Consultant

---

## Common mistakes to avoid

| Mistake | Why it breaks |
|---|---|
| Filling JSON Response Format on the Prescriber | Prescriber returns markdown for the user; structured output breaks rendering |
| Unchecking Patient context on the Consultant | FHIR header extraction silently no-ops |
| Publishing the Prescriber to marketplace | The Prescriber orchestrates YOUR flow; others should compose your Consultant, not your Prescriber |
| Skipping the Auditor | Hallucinated citations slip through |
| Short timeout (<60s) on the Prescriber | Chain: Prescriber → Consultant (analyze) → Consultant (verify) → Auditor (sufficiency + evidence + verify) can exceed 60s with FHIR round-trips |
| Omitting the disclaimer from the Prescriber prompt | Research-grade positioning is lost; judges will flag it |

---

## If PO requires a single SKILL.md upload per agent

Some PO deployments upload a file rather than accepting pasted text.
In that case:

```bash
cd hackathon/byo_agents
# Prescriber:  upload prescriber/SKILL.md
# Consultant:  upload consultant/SKILL.md
# Auditor:     upload auditor/SKILL.md
```

The files are self-contained and match the system-prompt + skill
contract PO expects.
