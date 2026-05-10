# Hackathon Session Plan

**Branch:** `hackathon/agents-assemble-2026`
**Deadline:** Mon, May 12, 2026 @ 8:30am IST (submission cuts off at 11:00pm EDT Mon May 11 = ~8:30am IST Tue May 12)
**Time budget:** ~14-15h from session start (May 10, 17:30 IST)

---

## Guardrails

1. **Zero changes to `main` swarm code.** Everything lives under `hackathon/`.
   The only exception is appending a single optional dependency line to the
   top-level `requirements.txt` (with a clear comment).
2. **Re-use, don't rebuild.** Every tool wraps the existing `SwarmRuntime`,
   `EvidenceRetriever`, `VerificationEngine`, or `ContextSufficiencyAgent`.
   No new reasoning logic.
3. **Every tool returns a typed FHIR resource OR a frozen dataclass.**
   Never a raw dict.
4. **SHARP is always on the critical path.** Every tool reads FHIR context
   via the shared adapter, and stamps it onto the existing `ProvenanceStamp`
   we emit.

---

## Milestones (in order)

### M1 — Scaffolding complete ✅
- `hackathon/README.md`, `PLAN.md`, `ARCHITECTURE.md`
- `hackathon/requirements.txt` with `fastmcp`, `fhir.resources`, `httpx`
- Empty package init files

### M2 — SHARP + FHIR adapters (deterministic, unit-testable)
- `hackathon/sharp/context.py` — mirrors `po_fastmcp.fhir_context.get_fhir_context`
  but plugs our `ProvenanceStamp` in on read.
- `hackathon/fhir/input.py` — map `Patient` (us-core-race/ethnicity) +
  `Observation` (PGx genotype via LOINC 100891-2) OR `MolecularSequence` →
  `(drug, gene, population, genotype)` tuple our SwarmRuntime accepts.
- `hackathon/fhir/output.py` — map our `UnifiedExecutionReport` →
  `DetectedIssue` + `ClinicalImpression` + `Provenance`.

### M3 — MCP Superpower server
- `hackathon/mcp_server/server.py` — `POFastMCP`-compatible server, registers
  all 5 tools, declares FHIR scopes.
- `hackathon/mcp_server/tools/*.py` — one file per tool. Each is a pure
  function wrapper around existing code.

### M4 — Tests
- Unit tests for SHARP context parsing, FHIR in/out round-trips.
- Integration test that spawns the MCP server in-process and invokes each
  tool via the MCP client SDK, asserts FHIR resource shape on the way out.

### M5 — Demo script
- `hackathon/demo.py` — simulates a Prompt Opinion prescriber agent calling
  our Superpower for a South Asian clopidogrel case. Prints the full FHIR
  DetectedIssue + Provenance chain. This is what the 3-min video will record.

### M6 — Submission copy
- `hackathon/SUBMISSION.md` — Devpost fields (inspiration, what-it-does,
  how-we-built, challenges, accomplishments, learned, what's-next, built-with).
- `hackathon/VIDEO_SCRIPT.md` — beat-by-beat 3-min script.

### M7 — Platform publish + video record (user task)
- Create Prompt Opinion account.
- Deploy MCP server to a public URL (ngrok / fly.io / Railway; pick one).
- Publish to Marketplace.
- Record 3-min video.
- Submit on Devpost.

---

## What I will NOT touch

- Anything under `agents/`, `core/`, `workflows/`, `retrieval/`,
  `knowledge_graph/`, `verification/`, `integrations/mcp/`, `interoperability/`,
  `population/`, `narrative/`, `guidelines/`, `rules/`, `datasets/`,
  `backend/`, `frontend/`, `demos/`, `tests/` (existing).
- `pyproject.toml` (ruff / mypy config).
- CI workflow.

If the integration exposes a bug in the main swarm, I'll document it as a
follow-up issue and use a narrow shim in `hackathon/` rather than editing
the main code paths.

---

## What I WILL touch

- `requirements.txt` — append `fastmcp>=3.2.4` and `fhir.resources>=8.2.0`
  as optional hackathon deps, clearly commented.
- New files under `hackathon/` only.
