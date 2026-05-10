"""Hackathon submission — Anukriti PGx MCP Superpower for Prompt Opinion.

Packaging layout (see hackathon/ARCHITECTURE.md for the full diagram):

    hackathon/sharp/       Prompt Opinion SHARP context extraction
    hackathon/fhir/        FHIR R4 input parsing + output synthesis
    hackathon/mcp_server/  FastMCP server exposing 5 PGx tools
    hackathon/tests/       Integration tests
    hackathon/demo.py      End-to-end demonstration

Nothing under this folder imports from elsewhere in the repo *except*
via the public APIs of the existing swarm modules (core/runtime,
agents/, verification/, etc.). The hackathon layer is strictly
additive; removing it leaves the main swarm untouched.
"""

__all__: list[str] = []
