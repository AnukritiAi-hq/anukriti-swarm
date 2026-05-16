# Anukriti PGx — BYO Agent Pack for Prompt Opinion

This folder contains ready-to-paste configuration and SKILL.md files
for the three Bring-Your-Own agents that compose with the Anukriti PGx
MCP Superpower on Prompt Opinion.

## The composition

```
 user / workspace query
          │
          ▼
 ┌──────────────────────┐
 │ 1. Prescriber Agent  │  user-facing; orchestrates the flow
 └────────┬─────────────┘
          │ consults
          ▼
 ┌──────────────────────┐
 │ 2. PGx Consultant    │  calls the 5 MCP tools, returns FHIR
 └────────┬─────────────┘
          │ audited by
          ▼
 ┌──────────────────────┐
 │ 3. Evidence Auditor  │  verifies citations + bias + rule IDs
 └──────────────────────┘
```

All three talk to your MCP server at `https://<host>/mcp` via Prompt
Opinion's tool-binding UI. The SKILL.md files below go into each
agent's **Agent Skills** section.

## Files

| File | Purpose |
|---|---|
| `prescriber/SKILL.md` | Clinical front-door; translates natural language → PGx tool calls |
| `consultant/SKILL.md` | Specialist; wraps the 5 Superpower tools with strict contracts |
| `auditor/SKILL.md` | Evidence + bias auditor; enforces "every refusal names a rule" |
| `TEST_SCENARIOS.md` | 6 paste-able test flows to validate the chain end-to-end |
| `RESPONSE_SCHEMAS.md` | JSON response-format schemas for each agent |

## Setup order in Prompt Opinion

1. Register your MCP server URL in **MCP Tools & Servers**.
2. Create the **PGx Consultant** first (no dependencies).
3. Create the **Evidence Auditor** next (consults the Consultant).
4. Create the **Prescriber** last (consults both).
5. Run the 6 test scenarios from `TEST_SCENARIOS.md`.

## Disclaimer

All three agents are research-grade. They return `DetectedIssue`-flavored
advisories for human review, never direct prescriptions. See the main
[`../../README.md`](../../README.md) safety architecture section.
