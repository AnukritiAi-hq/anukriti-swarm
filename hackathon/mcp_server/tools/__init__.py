"""All MCP tools exposed by the Anukriti PGx Superpower.

Each tool is a ``@tool()``-decorated callable. The module-level
``register_all_tools()`` binds them on the shared server.

Design notes
------------
- Every tool returns a plain ``dict`` (not a dataclass) because MCP's
  result envelope JSON-serialises the return value and typed FHIR
  resources already come out of our adapters as dicts.
- Every tool catches its own boundary-errors (``SharpContextMissing``,
  ``UnsupportedFHIRInput``) and returns a structured error shape
  rather than raising — this is what lets Prompt Opinion surface a
  helpful message to the end user instead of a 500.
- Every tool stamps the SHARP session id on the provenance chain so
  downstream audit can trace any output back to the EHR session.
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.tools import tool

from hackathon.mcp_server.tools.analyze import pgx_analyze_patient
from hackathon.mcp_server.tools.evidence import pgx_retrieve_evidence
from hackathon.mcp_server.tools.population import pgx_population_risk
from hackathon.mcp_server.tools.sufficiency import pgx_sufficiency_check
from hackathon.mcp_server.tools.verify import pgx_verify_recommendation


def register_all_tools(mcp: FastMCP) -> None:
    """Attach all Anukriti PGx tools to ``mcp``."""

    mcp.add_tool(pgx_analyze_patient)
    mcp.add_tool(pgx_population_risk)
    mcp.add_tool(pgx_retrieve_evidence)
    mcp.add_tool(pgx_verify_recommendation)
    mcp.add_tool(pgx_sufficiency_check)


__all__ = [
    "register_all_tools",
    "pgx_analyze_patient",
    "pgx_population_risk",
    "pgx_retrieve_evidence",
    "pgx_verify_recommendation",
    "pgx_sufficiency_check",
]
