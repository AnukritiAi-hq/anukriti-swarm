"""Anukriti Swarm — MCP infrastructure end-to-end demo.

Demonstrates every capability the MCP layer adds on top of the
deterministic-first orchestrator:

  1. MCP-enabled orchestration
        run three real queries, auto-persist each into all five
        MCP services (memory, traces, contexts, provenance, evidence)

  2. Memory persistence
        look up prior runs by (gene, drug, population)

  3. Provenance-aware reasoning
        walk the claim chain for a user-facing narrative back to its
        phenotype → evidence → CPIC rule → verification verdict

  4. Execution replay
        restore the frozen SwarmExecutionContext for a prior run,
        along with every evidence source it cited

  5. MCP observability
        one snapshot() call at the end shows tool-level call volume,
        success rate, and average latency

Runs without Mongo — the MCPClient default loader falls back to
``InMemoryBackend`` when ``MONGODB_URI`` isn't set. Set the env var
to persist across invocations.

Run: python -m demos.mcp_infrastructure_demo
"""

from __future__ import annotations

import os

from agents.orchestrator.gemini_orchestrator import GeminiOrchestrator
from integrations.mcp import (
    MCPClient,
    MCPPersistenceHook,
    MCPRetrieval,
)

# ---------------------------------------------------------------------------
# Formatting helpers — same aesthetic as demos/adk_demo.py
# ---------------------------------------------------------------------------

B, D, R = "\033[1m", "\033[2m", "\033[0m"
CYAN, GREEN, YELLOW, RED, MAGENTA, BLUE = (
    "\033[36m",
    "\033[32m",
    "\033[33m",
    "\033[31m",
    "\033[35m",
    "\033[34m",
)


def _rule(title: str = "", color: str = CYAN) -> None:
    if title:
        print(f"\n  {B}{color}  {title}{R}")
    print(f"  {B}{'─' * 68}{R}")


def _banner(title: str, subtitle: str = "") -> None:
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  {title}{R}")
    print(f"  {B}{'═' * 68}{R}")
    if subtitle:
        print(f"  {D}  {subtitle}{R}\n")


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "title": "CYP2C19 *2/*2 + clopidogrel in South Asian",
        "gene": "CYP2C19",
        "drug": "clopidogrel",
        "population": "SAS",
        "allele1": "*2",
        "allele2": "*2",
    },
    {
        "title": "CYP2D6 *4/*4 + codeine in European",
        "gene": "CYP2D6",
        "drug": "codeine",
        "population": "EUR",
        "allele1": "*4",
        "allele2": "*4",
    },
    {
        "title": "CYP2C19 *1/*1 + clopidogrel in African (comparator)",
        "gene": "CYP2C19",
        "drug": "clopidogrel",
        "population": "AFR",
        "allele1": "*1",
        "allele2": "*1",
    },
]


def run_demo() -> None:
    _banner(
        "🧬 ANUKRITI SWARM — MCP Infrastructure Demo",
        "Memory · Traces · Contexts · Provenance · Evidence — all persisted.",
    )

    # ----- Wiring ---------------------------------------------------
    # Let the loader pick: Mongo when MONGODB_URI set, in-memory otherwise.
    client = MCPClient()
    orchestrator = GeminiOrchestrator()
    hook = MCPPersistenceHook(client=client)
    retrieval = MCPRetrieval(client=client)

    print(f"  {D}  Backend mode:     {client.mode}{R}")
    print(f"  {D}  Registered tools: {len(client.list_tools())}{R}")
    print(f"  {D}  Services wired:   5  (memory, traces, contexts, provenance, evidence){R}")

    # -----------------------------------------------------------------
    # 1. MCP-enabled orchestration
    # -----------------------------------------------------------------
    _rule("1. MCP-enabled orchestration", GREEN)
    print(f"  {D}  Running {len(SCENARIOS)} scenarios, auto-persisting each.{R}\n")

    results = []
    for i, scn in enumerate(SCENARIOS, 1):
        result = orchestrator.run(
            gene=scn["gene"],
            drug=scn["drug"],
            population=scn["population"],
            allele1=scn["allele1"],
            allele2=scn["allele2"],
        )
        report = hook.persist(result)
        cid = result.context.correlation_id

        print(f"  {B}[{i}] {scn['title']}{R}")
        print(
            f"      correlation={cid}  phase={result.context.phase.value} "
            f"verify={result.verification_state.value}"
        )
        print(
            f"      persisted: mem={report.memory_stored} trace={report.trace_stored} "
            f"ctx={report.context_stored} "
            f"claims={report.claims_recorded} evidence={report.evidence_indexed}"
        )
        if report.errors:
            print(f"      {YELLOW}warnings: {len(report.errors)}{R}")
        results.append(result)

    print(f"\n  {D}  After persistence — service row counts:{R}")
    counts = retrieval.service_summary()
    for svc, n in counts.items():
        print(f"    {svc:<12} {n}")

    # -----------------------------------------------------------------
    # 2. Memory persistence — prior-run lookup
    # -----------------------------------------------------------------
    _rule("2. Memory persistence — prior-run lookup", YELLOW)
    print(
        f"  {D}  Query: 'give me every prior CYP2C19 + clopidogrel run'{R}\n"
    )

    prior = retrieval.lookup_prior(gene="CYP2C19", drug="clopidogrel")
    for p in prior:
        print(
            f"  • {p.get('correlation_id')}  pop={p.get('population') or '—':<5} "
            f"verify={p.get('verification_state')} "
            f"agents={len(p.get('active_agents', []))}"
        )

    print(f"\n  {D}  Query: 'population history for SAS'{R}\n")
    sas_hist = retrieval.population_history("SAS")
    for h in sas_hist:
        ds = h.get("deterministic_summary") or [{}]
        phen = ds[0].get("phenotype") if ds else "—"
        print(
            f"  • {h.get('correlation_id')}  {h.get('gene')}/{h.get('drug')}  → {phen}"
        )

    # -----------------------------------------------------------------
    # 3. Provenance-aware reasoning — walk a claim back to its evidence
    # -----------------------------------------------------------------
    _rule("3. Provenance-aware reasoning — walk the claim chain", MAGENTA)
    focus = results[0]
    fcid = focus.context.correlation_id
    print(f"  {D}  Focus run: {fcid} ({SCENARIOS[0]['title']}){R}\n")

    all_claims = retrieval.provenance.for_run(fcid).data or []
    print(f"  {D}  Total provenance records for this run: {len(all_claims)}{R}\n")
    for rec in all_claims:
        origin_color = MAGENTA if rec.get("origin") == "generative" else GREEN
        print(
            f"  • [{origin_color}{rec.get('origin', 'det')[:3]}{R}] "
            f"{B}{rec.get('rule_id'):<28}{R} "
            f"verdict={rec.get('verification_verdict'):<9} "
            f"conf={rec.get('confidence'):.2f}  "
            f"{rec.get('claim', '')[:60]}"
        )

    # Walk the narrative claim back to its root
    narratives = [r for r in all_claims if r.get("origin") == "generative"]
    if narratives:
        narrative_id = narratives[0]["claim_id"]
        print(f"\n  {D}  Walking chain from the narrative claim upward…{R}\n")
        chain = retrieval.provenance.chain(narrative_id).data or []
        for i, rec in enumerate(chain):
            arrow = "" if i == 0 else "    ↑ wasDerivedFrom"
            if arrow:
                print(f"  {D}{arrow}{R}")
            print(
                f"  [{i}] {B}{rec.get('rule_id')}{R}\n"
                f"      agent={rec.get('generating_agent')}\n"
                f"      claim={rec.get('claim', '')[:80]}\n"
                f"      evidence={rec.get('evidence_sources') or '[]'}"
            )

    # -----------------------------------------------------------------
    # 4. Execution replay — rehydrate a prior run
    # -----------------------------------------------------------------
    _rule("4. Execution replay — rehydrate context for inspection", BLUE)
    print(f"  {D}  Replaying run {fcid}…{R}\n")

    bundle = retrieval.replay(fcid)
    print(f"  • lookup.exists:              {bundle.lookup.exists}")
    print(f"  • lookup.summary:             {bundle.lookup.summary()}")
    print(
        f"  • evidence_by_source:         "
        f"{len(bundle.evidence_by_source)} source(s) resolved"
    )
    for sid, doc in bundle.evidence_by_source.items():
        title = doc.get("title") or "(no title)"
        print(f"      - {sid}  {D}{title[:50]}{R}")

    restored = bundle.restore_context()
    if restored is not None:
        print(f"\n  {D}  restore_context() returned a live SwarmExecutionContext:{R}")
        print(f"    type:       {type(restored).__name__}")
        print(f"    query:      {restored.query!r}")
        print(f"    gene/drug:  {restored.gene}/{restored.drug} in {restored.population}")
        print(f"    agents:     {restored.active_agents}")
        print(f"    evidence:   {restored.evidence_refs}")
        print(f"    verdict:    {restored.verification_state.value}")
    else:
        print(f"\n  {YELLOW}  (restore_context returned None — no snapshot found){R}")

    # -----------------------------------------------------------------
    # 5. MCP observability — tool-level call metrics
    # -----------------------------------------------------------------
    _rule("5. MCP observability snapshot", CYAN)

    snap = client.snapshot()
    print(
        f"  total_calls={snap['calls']}  failures={snap['failures']}  "
        f"success_rate={snap['success_rate']:.2%}  "
        f"avg_latency={snap['avg_latency_ms']:.2f}ms"
    )
    print(f"  {D}  backend={snap['backend_mode']}  started_at={snap['started_at']}{R}")
    print(f"\n  {D}  Per-tool breakdown:{R}")

    # Sort by call volume desc for readability
    by_tool = sorted(
        snap["by_tool"].items(), key=lambda kv: kv[1]["calls"], reverse=True
    )
    for name, stats in by_tool:
        fail_marker = (
            f"  {RED}fail={stats['failures']}{R}" if stats["failures"] else ""
        )
        print(
            f"    {name:<28} calls={stats['calls']:>3} "
            f"avg={stats['avg_latency_ms']:>6.2f}ms"
            f"{fail_marker}"
        )

    # -----------------------------------------------------------------
    # Done
    # -----------------------------------------------------------------
    print(f"\n  {B}{'═' * 68}{R}")
    print(
        f"  {B}{CYAN}  {len(results)} runs · "
        f"{counts['executions']} memory · "
        f"{counts['traces']} traces · "
        f"{counts['contexts']} contexts · "
        f"{counts['provenance']} claims · "
        f"{counts['evidence']} evidence{R}"
    )
    print(f"  {B}{CYAN}  MCP remembers. Provenance explains. Replay rehydrates.{R}")
    print(f"  {B}{'═' * 68}{R}\n")

    # Clean up any backend resources (Mongo client pool in particular).
    client.close()


if __name__ == "__main__":
    run_demo()
