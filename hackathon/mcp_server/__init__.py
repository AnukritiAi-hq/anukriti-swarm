"""MCP server package — Anukriti PGx Superpower for Prompt Opinion.

Entry point: ``python -m hackathon.mcp_server`` launches the server
on ``http://0.0.0.0:9000/mcp`` (configurable via env vars).

All 5 tools are registered on the shared ``POAnukritMCP`` instance:

    pgx_analyze_patient         end-to-end analysis (FHIR in → FHIR out)
    pgx_population_risk         allele frequency + prevalence (no patient)
    pgx_retrieve_evidence       cited CPIC/PubMed passages
    pgx_verify_recommendation   6-check verification of a proposed rec
    pgx_sufficiency_check       can we safely answer this?

The server subclasses ``POFastMCP``-style plumbing (declares the
``ai.promptopinion/fhir-context`` capability extension with the scopes
our tools need) so Prompt Opinion's platform can discover it with no
extra configuration.
"""

from hackathon.mcp_server.server import build_server

__all__ = ["build_server"]
