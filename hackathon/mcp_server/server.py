"""FastMCP server entry point for the Anukriti PGx Superpower.

Declares the Prompt Opinion SHARP capability extension
(``ai.promptopinion/fhir-context``) with the FHIR scopes our tools
need:

    patient/Patient.rs            read + search the patient's demographics
                                  (for ancestry inference from us-core-race)
    patient/Observation.rs        read + search PGx Observations
                                  (LOINC 53040-2, 84413-4, 81252-9, etc.)
    patient/MolecularSequence.rs  read-only; variant-calling is out of scope
    patient/Condition.rs          read-only; used for conflict flags in
                                  pgx_verify_recommendation

All scopes are declared non-required so tools can run on explicit
arguments when no patient is active.

Usage
-----

Programmatic (tests + AWS entry point):

    from hackathon.mcp_server import build_server
    mcp = build_server()
    mcp.run(transport="http", host="0.0.0.0", port=9000)

CLI:

    python -m hackathon.mcp_server
    # or
    python -m hackathon.mcp_server.server
"""

from __future__ import annotations

import os
import signal
import sys
from types import MethodType
from typing import Any

from fastmcp import FastMCP


# -----------------------------------------------------------------------------
# SHARP capability extension
# -----------------------------------------------------------------------------


_SHARP_CAPABILITY = "ai.promptopinion/fhir-context"

# One entry per FHIR resource type this Superpower reads. Each entry
# mirrors the ``{"name": "...", "required": bool}`` shape po-fastmcp
# uses so Prompt Opinion's platform recognises us without any custom
# handling. "rs" = read + search. "rsu" = read + search + update.
# We never write FHIR resources, so no "u" appears.
_ANUKRITI_FHIR_SCOPES: list[dict[str, Any]] = [
    {
        "name": "patient/Patient.rs",
        "required": False,
        # Populated via ``_mcp_server.get_capabilities`` below; the
        # ``description`` is ours (not a FHIR field) and is dropped
        # before being sent over the wire — we keep it here because
        # the FastMCP extension helper ignores unknown keys.
        "description": "Read patient demographics for ancestry (us-core-race)",
    },
    {
        "name": "patient/Observation.rs",
        "required": False,
        "description": "Read PGx genotype Observations (LOINC 53040-2, 84413-4, ...)",
    },
    {
        "name": "patient/MolecularSequence.rs",
        "required": False,
        "description": "Read-only; variant-calling is upstream of this server",
    },
    {
        "name": "patient/Condition.rs",
        "required": False,
        "description": "Read conditions for pgx_verify_recommendation conflict flags",
    },
]


def _install_sharp_extension(mcp: FastMCP) -> None:
    """Declare the SHARP capability extension on the MCP handshake.

    Follows the same monkey-patch pattern as
    ``po_fastmcp.server._add_fhir_context_extension`` — override
    ``mcp._mcp_server.get_capabilities`` so every handshake response
    advertises our scopes.
    """

    original = mcp._mcp_server.get_capabilities
    scopes = [
        {"name": str(s["name"]), "required": bool(s.get("required", False))}
        for s in _ANUKRITI_FHIR_SCOPES
    ]

    def get_capabilities(self, notification_options, experimental_capabilities):
        caps = original(notification_options, experimental_capabilities)
        existing = getattr(caps, "extensions", None) or {}
        caps.extensions = {
            **existing,
            _SHARP_CAPABILITY: {"scopes": scopes},
        }
        return caps

    mcp._mcp_server.get_capabilities = MethodType(
        get_capabilities, mcp._mcp_server
    )


# -----------------------------------------------------------------------------
# Server factory
# -----------------------------------------------------------------------------


def build_server() -> FastMCP:
    """Construct + configure the FastMCP server for the Superpower.

    The returned server has:
        - All 5 PGx tools registered
        - The SHARP extension advertised on the MCP handshake
        - Descriptive name + instructions visible in the registry

    Called by the ``__main__`` CLI and by integration tests.
    """

    mcp = FastMCP(
        name="Anukriti PGx — Pharmacogenomic Intelligence",
        instructions=(
            "Deterministic, population-aware pharmacogenomic reasoning. "
            "Returns FHIR R5 DetectedIssue + ClinicalImpression + Provenance "
            "resources for drug-gene-population-genotype tuples. "
            "Research use only — never direct prescriptions."
        ),
    )

    _install_sharp_extension(mcp)

    # Lazy import so the tools module isn't loaded at the server-
    # factory level unless we actually build a server (keeps unit
    # tests that only need the server import fast).
    from hackathon.mcp_server.tools import register_all_tools

    register_all_tools(mcp)

    return mcp


# -----------------------------------------------------------------------------
# Module-level app — used by `python -m hackathon.mcp_server.server`,
# Docker, AWS App Runner, and the uvicorn ASGI path.
# -----------------------------------------------------------------------------


mcp = build_server()


def _env_host() -> str:
    return os.environ.get("ANUKRITI_MCP_HOST", "0.0.0.0")


def _env_port() -> int:
    return int(os.environ.get("ANUKRITI_MCP_PORT", "9000"))


def main() -> None:
    """Run the server on the configured host/port."""

    host = _env_host()
    port = _env_port()

    # Handle SIGTERM cleanly when running under Docker / systemd.
    def _graceful_exit(signum, frame):  # pragma: no cover — runtime only
        print(f"\n[anukriti-pgx] received signal {signum}, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGTERM, _graceful_exit)

    try:
        print(f"[anukriti-pgx] starting MCP server on http://{host}:{port}/mcp")
        print("[anukriti-pgx] press Ctrl+C to stop")
        mcp.run(transport="http", host=host, port=port)
    except KeyboardInterrupt:
        print("\n[anukriti-pgx] server stopped.")


if __name__ == "__main__":
    main()
