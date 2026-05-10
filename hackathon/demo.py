"""End-to-end demonstration for the 3-minute video.

Simulates a Prompt Opinion prescriber agent invoking our MCP
Superpower for the flagship South-Asian clopidogrel scenario. Prints
the full FHIR bundle (DetectedIssue + ClinicalImpression +
Provenance) plus the population equity narrative.

Run:
    python -m hackathon.demo

The demo uses the in-memory FastMCP client transport, so it does not
require the server to be running separately. This is what the video
records locally. In production (on Prompt Opinion), a real A2A agent
would invoke the same tools over HTTP.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastmcp import Client

from hackathon.mcp_server import build_server


# ANSI colour codes — mirror the existing demos/showcase.py aesthetic.
class _C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"


# ---------------------------------------------------------------------
# Scenario — the story we tell
# ---------------------------------------------------------------------


# A synthetic FHIR Patient + Observation describing a South Asian
# patient who had a PGx test showing CYP2C19 *2/*2. This is what a
# Prompt Opinion A2A prescriber agent would send us when it looks at
# the patient's chart and sees a pending clopidogrel order.

US_CORE_RACE_URL = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race"

DEMO_PATIENT: dict[str, Any] = {
    "resourceType": "Patient",
    "id": "demo-patient-priya",
    "name": [{"family": "Patel", "given": ["Priya"]}],
    "gender": "female",
    "birthDate": "1961-07-14",
    "extension": [
        {
            "url": US_CORE_RACE_URL,
            "extension": [
                {
                    "url": "ombCategory",
                    "valueCoding": {
                        "system": "urn:oid:2.16.840.1.113883.6.238",
                        "code": "2028-9",
                        "display": "Asian",
                    },
                },
                {
                    "url": "detailed",
                    "valueCoding": {
                        "system": "urn:oid:2.16.840.1.113883.6.238",
                        "code": "2032-3",
                        "display": "Asian Indian",
                    },
                },
                {"url": "text", "valueString": "Asian Indian"},
            ],
        }
    ],
}

DEMO_OBSERVATION: dict[str, Any] = {
    "resourceType": "Observation",
    "id": "demo-obs-cyp2c19",
    "status": "final",
    "category": [
        {
            "coding": [
                {
                    "system": (
                        "http://terminology.hl7.org/CodeSystem/observation-category"
                    ),
                    "code": "laboratory",
                    "display": "Laboratory",
                }
            ]
        }
    ],
    "code": {
        "coding": [
            {
                "system": "http://loinc.org",
                "code": "53040-2",
                "display": "Genetic disease analysis overall interpretation",
            }
        ],
        "text": "CYP2C19 genotype result",
    },
    "subject": {"reference": "Patient/demo-patient-priya"},
    "effectiveDateTime": "2026-04-01T10:30:00Z",
    "valueString": "CYP2C19 *2/*2 (Poor Metabolizer)",
}


# ---------------------------------------------------------------------
# Demo sections
# ---------------------------------------------------------------------


def _header(title: str) -> None:
    print()
    print(f"  {_C.BOLD}{_C.CYAN}{'═' * 70}{_C.RESET}")
    print(f"  {_C.BOLD}{_C.CYAN}  {title}{_C.RESET}")
    print(f"  {_C.BOLD}{_C.CYAN}{'═' * 70}{_C.RESET}")


def _step(n: int, title: str) -> None:
    print()
    print(
        f"  {_C.BOLD}[Step {n}] {title}{_C.RESET}"
    )
    print(f"  {_C.DIM}{'─' * 68}{_C.RESET}")


def _kv(key: str, value: str, colour: str = _C.CYAN) -> None:
    print(f"    {_C.DIM}{key:<22}{_C.RESET}  {colour}{value}{_C.RESET}")


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------


async def run_demo() -> None:
    _header("🧬 Anukriti PGx — MCP Superpower Demo")

    print(
        f"\n  {_C.DIM}Scenario: a Prompt Opinion A2A prescriber agent sees a pending{_C.RESET}"
    )
    print(
        f"  {_C.DIM}clopidogrel order for a 64-year-old South Asian patient. It{_C.RESET}"
    )
    print(
        f"  {_C.DIM}invokes our Superpower to check: will this drug work?{_C.RESET}"
    )

    # -----------------------------------------------------------------
    # Step 1: show the raw FHIR inputs
    # -----------------------------------------------------------------
    _step(1, "📋 FHIR context from the EHR")
    _kv("Patient", f"{DEMO_PATIENT['id']} (Priya Patel, 64F)")
    _kv("Ancestry", "Asian Indian → SAS super-population", colour=_C.YELLOW)
    _kv("Observation", f"{DEMO_OBSERVATION['id']} (LOINC 53040-2)")
    _kv("Reported value", DEMO_OBSERVATION["valueString"], colour=_C.YELLOW)
    _kv("Pending order", "clopidogrel 75 mg daily (post-PCI)", colour=_C.RED)

    # -----------------------------------------------------------------
    # Step 2: connect to the MCP server (in-memory)
    # -----------------------------------------------------------------
    _step(2, "🔌 Connect to the Anukriti PGx MCP server")
    mcp = build_server()

    async with Client(mcp) as client:
        tools = await client.list_tools()
        _kv("Server", mcp.name)
        _kv("Tools exposed", str(len(tools)))
        for t in tools:
            print(f"      · {_C.CYAN}{t.name}{_C.RESET}")

        # -------------------------------------------------------------
        # Step 3: sufficiency check — can we answer this safely?
        # -------------------------------------------------------------
        _step(3, "✓ Ask the Superpower: can we safely answer this?")
        suff_result = await client.call_tool(
            "pgx_sufficiency_check",
            {
                "drug": "clopidogrel",
                "gene": "CYP2C19",
                "patient": DEMO_PATIENT,
                "observations": [DEMO_OBSERVATION],
            },
        )
        suff = suff_result.data
        _kv("allowsSynthesis", str(suff["allowsSynthesis"]), colour=_C.GREEN)
        _kv(
            "rule IDs fired",
            ", ".join(suff["ruleIds"]) or "none",
            colour=_C.GREEN,
        )
        if suff.get("blockingReason"):
            _kv("block reason", suff["blockingReason"], colour=_C.RED)

        # -------------------------------------------------------------
        # Step 4: the flagship analysis
        # -------------------------------------------------------------
        _step(4, "🧠 Run the full 5-stage swarm analysis")
        analysis_result = await client.call_tool(
            "pgx_analyze_patient",
            {
                "drug": "clopidogrel",
                "gene": "CYP2C19",
                "patient": DEMO_PATIENT,
                "observations": [DEMO_OBSERVATION],
                "question": (
                    "Will clopidogrel work for this patient? If not, suggest "
                    "alternatives with CPIC evidence."
                ),
            },
        )
        analysis = analysis_result.data

        if not analysis.get("ok"):
            print(
                f"    {_C.RED}ERROR:{_C.RESET} "
                f"{analysis.get('error', {}).get('message', 'unknown')}"
            )
            return

        _kv("duration", f"{analysis['durationMs']:.1f} ms")
        _kv("specialists", str(len(analysis["activatedAgents"])))
        for agent in analysis["activatedAgents"]:
            print(f"      · {_C.CYAN}{agent}{_C.RESET}")

        # -------------------------------------------------------------
        # Step 5: headline finding
        # -------------------------------------------------------------
        _step(5, "🎯 The answer")
        print()
        print(f"    {_C.BOLD}{_C.RED}Recommendation strength: {analysis['strength']}{_C.RESET}")
        print()
        # Wrap the recommendation for readability
        rec = analysis["recommendation"]
        for line in _wrap(rec, 62):
            print(f"    {_C.BOLD}{line}{_C.RESET}")

        # -------------------------------------------------------------
        # Step 6: population equity angle
        # -------------------------------------------------------------
        _step(6, "🌍 Why ancestry matters here")
        pop_result = await client.call_tool(
            "pgx_population_risk",
            {"gene": "CYP2C19", "allele": "*2", "population": "SAS"},
        )
        pop = pop_result.data
        _kv("CYP2C19*2 in SAS", f"{pop['frequency']*100:.1f}%", colour=_C.YELLOW)
        _kv("Rarity class", pop["rarity"], colour=_C.YELLOW)

        eur_pop = await client.call_tool(
            "pgx_population_risk",
            {"gene": "CYP2C19", "allele": "*2", "population": "EUR"},
        )
        eur = eur_pop.data
        _kv("CYP2C19*2 in EUR", f"{eur['frequency']*100:.1f}%", colour=_C.CYAN)

        afr_pop = await client.call_tool(
            "pgx_population_risk",
            {"gene": "CYP2C19", "allele": "*2", "population": "AFR"},
        )
        afr = afr_pop.data
        _kv("CYP2C19*2 in AFR", f"{afr['frequency']*100:.1f}%", colour=_C.CYAN)

        print()
        print(
            f"    {_C.DIM}14% of South Asians are Poor Metabolizers — 2x the EUR rate.{_C.RESET}"
        )
        print(
            f"    {_C.DIM}Today's EHRs prescribe clopidogrel at the same rate in both.{_C.RESET}"
        )

        # -------------------------------------------------------------
        # Step 7: FHIR resources emitted
        # -------------------------------------------------------------
        _step(7, "📦 FHIR resources the Superpower returns")

        di = analysis["detectedIssue"]
        ci = analysis["clinicalImpression"]
        prov = analysis["provenance"]

        _kv("DetectedIssue", di["id"])
        _kv("  severity", di["severity"], colour=_C.RED)
        _kv("  evidence refs", str(len(di.get("evidence", []))))
        _kv("  mitigations", str(len(di.get("mitigation", []))))

        _kv("ClinicalImpression", ci["id"])
        _kv("  status", ci["status"])
        _kv("  findings", str(len(ci["finding"])))
        _kv("  protocols", str(len(ci.get("protocol", []))))

        _kv("Provenance", prov["id"])
        _kv("  targets", str(len(prov["target"])))
        _kv("  agents", str(len(prov["agent"])))
        _kv("  entities (PMIDs)", str(len(prov.get("entity", []))))

        # -------------------------------------------------------------
        # Step 8: show one real FHIR resource pretty-printed
        # -------------------------------------------------------------
        _step(8, "🔍 Peek: the emitted DetectedIssue resource")
        print()
        snippet = {
            "resourceType": di["resourceType"],
            "id": di["id"],
            "status": di["status"],
            "severity": di["severity"],
            "category": di.get("category"),
            "subject": di.get("subject"),
            "implicated": di["implicated"],
            "detail": _truncate(di["detail"], 140),
            "evidence": [
                {"code": [{"text": e["code"][0].get("text", "?")}]}
                for e in di.get("evidence", [])
            ],
            "mitigation": di.get("mitigation", []),
        }
        indented = json.dumps(snippet, indent=2).splitlines()
        for line in indented:
            print(f"    {_C.DIM}{line}{_C.RESET}")

        # -------------------------------------------------------------
        # Step 9: one-line audit trail summary
        # -------------------------------------------------------------
        _step(9, "🧾 Provenance / audit trail")
        for agent in prov["agent"]:
            who = agent.get("who", {})
            ident = who.get("identifier", {}).get("value", "")
            display = who.get("display", ident)
            print(f"    {_C.DIM}  ↦ {display}{_C.RESET}  "
                  f"{_C.CYAN}{ident[:64]}{_C.RESET}")

        print()
        _header("✅ Demo complete — every claim cited, every decision auditable")
        print()


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    length = 0
    for word in words:
        wlen = len(word)
        if length + wlen + (1 if current else 0) > width:
            if current:
                lines.append(" ".join(current))
            current = [word]
            length = wlen
        else:
            current.append(word)
            length += wlen + (1 if len(current) > 1 else 0)
    if current:
        lines.append(" ".join(current))
    return lines


if __name__ == "__main__":
    asyncio.run(run_demo())
