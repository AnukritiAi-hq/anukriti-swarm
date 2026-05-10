"""Integration tests for the Anukriti PGx MCP server.

We use FastMCP's in-memory client transport — pass the server
instance straight to ``Client(...)`` and tool calls round-trip
through the full MCP protocol without needing a network socket.

Each test asserts:
  1. The tool is discoverable on the server.
  2. Calling it with realistic arguments returns an ``ok=True``
     envelope.
  3. The returned payload has the expected top-level shape.

The SHARP header path (``get_sharp_context()`` via
``fastmcp.server.dependencies``) is exercised separately in
``test_sharp.py`` and via the FHIR round-trip test in ``test_fhir.py``.
Here we focus on the *tool contract*.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastmcp import Client

from hackathon.mcp_server import build_server


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def mcp_server():
    return build_server()


@pytest_asyncio.fixture
async def client(mcp_server):
    async with Client(mcp_server) as c:
        yield c


# =============================================================================
# Discovery
# =============================================================================


@pytest.mark.asyncio
async def test_all_five_tools_registered(client):
    tools = await client.list_tools()
    names = {t.name for t in tools}

    assert names == {
        "pgx_analyze_patient",
        "pgx_population_risk",
        "pgx_retrieve_evidence",
        "pgx_verify_recommendation",
        "pgx_sufficiency_check",
    }


@pytest.mark.asyncio
async def test_server_advertises_sharp_capability(mcp_server):
    """The SHARP extension must be declared on the MCP handshake."""

    class _NotificationOptions:
        prompts_changed = False
        resources_changed = False
        tools_changed = False

    caps = mcp_server._mcp_server.get_capabilities(_NotificationOptions(), None)
    extensions = getattr(caps, "extensions", None) or {}

    assert "ai.promptopinion/fhir-context" in extensions
    scope_names = {s["name"] for s in extensions["ai.promptopinion/fhir-context"]["scopes"]}
    assert "patient/Patient.rs" in scope_names
    assert "patient/Observation.rs" in scope_names


# =============================================================================
# pgx_population_risk
# =============================================================================


@pytest.mark.asyncio
async def test_population_risk_happy_path(client):
    result = await client.call_tool(
        "pgx_population_risk",
        {"gene": "CYP2C19", "allele": "*2", "population": "SAS"},
    )
    payload = result.data

    assert payload["ok"] is True
    assert payload["population"] == "SAS"
    assert payload["gene"] == "CYP2C19"
    assert payload["allele"] == "*2"
    assert payload["frequency"] is not None
    assert payload["frequency"] > 0.3  # ~36% in SAS
    assert "clinicalNote" in payload
    assert isinstance(payload["prevalenceByPhenotype"], list)


@pytest.mark.asyncio
async def test_population_risk_unsupported_population(client):
    result = await client.call_tool(
        "pgx_population_risk",
        {"gene": "CYP2C19", "allele": "*2", "population": "MARS"},
    )
    payload = result.data

    assert payload["ok"] is False
    assert payload["error"]["kind"] == "unsupported_population"


# =============================================================================
# pgx_retrieve_evidence
# =============================================================================


@pytest.mark.asyncio
async def test_retrieve_evidence_returns_cited_claims(client):
    result = await client.call_tool(
        "pgx_retrieve_evidence",
        {"gene": "CYP2C19", "drug": "clopidogrel", "population": "SAS"},
    )
    payload = result.data

    assert payload["ok"] is True
    assert isinstance(payload["claims"], list)
    assert len(payload["claims"]) >= 1
    assert 0.0 <= payload["groundingScore"] <= 1.0
    assert payload["totalRetrieved"] >= 0

    # Every claim must have citations (grounded or not).
    for claim in payload["claims"]:
        assert "citations" in claim
        assert "claim" in claim
        assert "grounded" in claim


# =============================================================================
# pgx_verify_recommendation
# =============================================================================


@pytest.mark.asyncio
async def test_verify_recommendation_passes_with_good_input(client):
    result = await client.call_tool(
        "pgx_verify_recommendation",
        {
            "agent_id": "demo-agent",
            "gene": "CYP2C19",
            "drug": "clopidogrel",
            "recommendation_text": (
                "Use prasugrel or ticagrelor instead of clopidogrel for "
                "CYP2C19 Poor Metabolizers."
            ),
            "recommendation_strength": "strong",
            "guideline_id": "CPIC:CYP2C19:clopidogrel:2022",
            "pmid": "34032273",
            "confidence": 0.95,
            "population": "SAS",
        },
    )
    payload = result.data

    assert payload["ok"] is True
    assert payload["verdict"] in {"pass", "warn", "fail"}
    assert "checks" in payload
    assert len(payload["checks"]) >= 3  # at least boundary + provenance + hallucination


@pytest.mark.asyncio
async def test_verify_recommendation_flags_unknown_gene(client):
    result = await client.call_tool(
        "pgx_verify_recommendation",
        {
            "agent_id": "demo-agent",
            "gene": "FAKE_GENE",
            "drug": "clopidogrel",
            "recommendation_text": "Use X.",
            "recommendation_strength": "strong",
            "confidence": 0.5,
        },
    )
    payload = result.data

    # Doesn't have to fail outright, but the hallucination check should
    # NOT be a silent pass. Look for it explicitly.
    assert payload["ok"] is True
    halluc = next(
        (c for c in payload["checks"] if "hallucin" in c["name"].lower()),
        None,
    )
    assert halluc is not None
    assert halluc["verdict"] in {"warn", "fail"}


# =============================================================================
# pgx_sufficiency_check
# =============================================================================


@pytest.mark.asyncio
async def test_sufficiency_check_clopidogrel_sas_case(client):
    """The flagship clopidogrel/SAS case must be judged 'sufficient'.

    If this ever regresses, it means the evidence fabric has drifted
    and the swarm wouldn't recommend the CPIC-strong action.
    """
    result = await client.call_tool(
        "pgx_sufficiency_check",
        {
            "drug": "clopidogrel",
            "gene": "CYP2C19",
            "population": "SAS",
            "genotype": "*2/*2",
        },
    )
    payload = result.data

    assert payload["ok"] is True
    assert payload["allowsSynthesis"] is True
    # The checkpoint decision should be a positive one. The rule id
    # set is non-empty either way.
    assert isinstance(payload["ruleIds"], list)
    assert len(payload["ruleIds"]) >= 1


# =============================================================================
# pgx_analyze_patient  — the flagship
# =============================================================================


@pytest.mark.asyncio
async def test_analyze_patient_explicit_args(client):
    """Analyze a SAS clopidogrel case with explicit population+genotype.

    This is the tightest possible path — no FHIR parsing, just the
    args straight through to the swarm and out as FHIR.
    """
    result = await client.call_tool(
        "pgx_analyze_patient",
        {
            "drug": "clopidogrel",
            "gene": "CYP2C19",
            "population": "SAS",
            "genotype": "*2/*2",
        },
    )
    payload = result.data

    assert payload["ok"] is True
    assert payload["allowsSynthesis"] is True

    di = payload["detectedIssue"]
    assert di["resourceType"] == "DetectedIssue"
    assert di["severity"] in {"high", "moderate", "low"}
    assert di["implicated"][0]["display"] == "clopidogrel"

    ci = payload["clinicalImpression"]
    assert ci["resourceType"] == "ClinicalImpression"
    assert ci["summary"]

    prov = payload["provenance"]
    assert prov["resourceType"] == "Provenance"
    assert len(prov["target"]) == 2

    # Must have activated multiple specialists
    assert len(payload["activatedAgents"]) >= 3

    # Must carry the recommendation text
    assert payload["recommendation"]
    assert payload["strength"]


@pytest.mark.asyncio
async def test_analyze_patient_fhir_in_path(client):
    """Analyze via FHIR Patient + Observation (the Prompt Opinion flow)."""
    us_core_race = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race"
    patient = {
        "resourceType": "Patient",
        "id": "demo-patient-001",
        "extension": [
            {
                "url": us_core_race,
                "extension": [
                    {
                        "url": "ombCategory",
                        "valueCoding": {"code": "2028-9", "display": "Asian"},
                    },
                    {
                        "url": "detailed",
                        "valueCoding": {"code": "2032-3", "display": "Asian Indian"},
                    },
                ],
            }
        ],
    }
    obs = {
        "resourceType": "Observation",
        "id": "demo-obs-001",
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "53040-2",
                    "display": "Genetic disease analysis",
                }
            ],
        },
        "valueString": "CYP2C19 *2/*2",
    }

    result = await client.call_tool(
        "pgx_analyze_patient",
        {
            "drug": "clopidogrel",
            "gene": "CYP2C19",
            "patient": patient,
            "observations": [obs],
        },
    )
    payload = result.data

    assert payload["ok"] is True
    # Should have inferred SAS from the Asian Indian detail code.
    assert "SAS" in payload["clinicalImpression"]["description"]
    # DetectedIssue.subject should reference our patient.
    assert payload["detectedIssue"]["subject"]["reference"] == (
        "Patient/demo-patient-001"
    )


@pytest.mark.asyncio
async def test_analyze_patient_missing_prerequisite_returns_structured_error(
    client,
):
    """Missing population + no FHIR yields a structured error, not a 500."""
    result = await client.call_tool(
        "pgx_analyze_patient",
        {"drug": "clopidogrel", "gene": "CYP2C19"},
    )
    payload = result.data

    assert payload["ok"] is False
    assert payload["error"]["kind"] == "missing_prerequisite"
    # The message must be actionable — tell the caller how to fix it.
    assert "population" in payload["error"]["message"].lower()
