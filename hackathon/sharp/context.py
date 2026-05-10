"""SHARP context adapter — Prompt Opinion FHIR headers → SwarmRuntime context.

**SHARP** is the Prompt Opinion-defined convention for passing healthcare
session credentials (FHIR server URL, bearer token, patient ID) through
MCP tool calls without polluting tool arguments. See
https://github.com/prompt-opinion/po-fastmcp for the reference client.

This module mirrors the ``po_fastmcp.fhir_context`` reader so our MCP
tools read SHARP context the same way every Prompt Opinion-compatible
MCP server does, and adds two Anukriti-specific concerns:

1. **Provenance stamping.** The existing swarm's ``ProvenanceStamp``
   model (see ``integrations/mcp/models.py``) records the source of
   every claim. Every tool call that uses SHARP context records the
   session id on the stamp so the resulting FHIR ``Provenance`` resource
   traces back to the exact EHR session the MCP call came from.

2. **Graceful degradation.** Not every tool needs a patient. Some PGx
   queries are population-level ("what's the CYP2C19*2 frequency in
   SAS?"). The adapter exposes two entry points:

       get_sharp_context()        optional — returns None when headers
                                   are absent
       require_sharp_context()    raises SharpContextMissing when
                                   patient headers are required

The three headers read are exactly the set Prompt Opinion's platform
emits (see ``po_fastmcp.fhir_context``):

    x-fhir-server-url   base URL for the upstream FHIR R4 server
    x-fhir-access-token bearer token with patient/* scopes
    x-patient-id        currently-selected patient

Additional optional headers Anukriti understands (forward-compatible):

    x-session-id        opaque session id for audit linkage
    x-fhir-issuer       FHIR server iss URI (for SMART-on-FHIR linkage)

None of these are required by the Prompt Opinion platform today; they
are read defensively so downstream providers can populate them without
requiring server-side changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Header names — must match po_fastmcp verbatim so Prompt Opinion's
# platform hits our adapter identically to any other Superpower.
_FHIR_SERVER_URL_HEADER = "x-fhir-server-url"
_FHIR_ACCESS_TOKEN_HEADER = "x-fhir-access-token"
_PATIENT_ID_HEADER = "x-patient-id"

# Optional headers for richer provenance linkage. Not defined by the
# Prompt Opinion platform today; read defensively.
_SESSION_ID_HEADER = "x-session-id"
_FHIR_ISSUER_HEADER = "x-fhir-issuer"


class SharpContextMissing(RuntimeError):
    """Raised when a tool requires SHARP context that is not available.

    Tools call ``require_sharp_context()`` to enforce patient-scope
    headers. Callers without an active patient session get this error
    mapped to a structured MCP error rather than a 500.
    """


@dataclass(frozen=True)
class SharpContext:
    """Frozen SHARP context for one MCP tool invocation.

    Mirrors ``po_fastmcp.fhir_context.FhirContext`` on the first three
    fields and adds two optional audit fields. All fields are frozen
    so a context can be passed into deeper reasoning layers without
    accidental mutation.
    """

    url: str
    token: str
    patient_id: str | None

    # Optional — absence is not an error.
    session_id: str | None = None
    issuer: str | None = None

    # Preserved headers for downstream audit — never mutated.
    raw_headers: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def has_patient(self) -> bool:
        """True when a patient scope is active on this context."""
        return bool(self.patient_id)

    def provenance_agent_id(self) -> str:
        """Return a stable agent id for FHIR Provenance.agent.who.

        Encodes the session+patient scope so every Provenance resource
        we emit unambiguously identifies the Prompt Opinion session
        that produced it.
        """
        session_part = self.session_id or "session-unknown"
        patient_part = self.patient_id or "no-patient"
        return f"anukriti-pgx:po-session/{session_part}:patient/{patient_part}"


# ---------------------------------------------------------------------
# Public API — two entry points
# ---------------------------------------------------------------------


def get_sharp_context(
    headers: dict[str, str] | None = None,
) -> SharpContext | None:
    """Read SHARP context from request headers; return None if absent.

    When ``headers`` is not provided, the function attempts to read
    the current FastMCP request headers via
    ``fastmcp.server.dependencies.get_http_headers``. Passing
    ``headers`` explicitly is useful for tests and for the local
    demo script (``hackathon/demo.py``) that invokes tools without an
    HTTP server running.

    Returns ``None`` when required headers (url + token) are missing.
    Patient id is optional — population-level tools accept a context
    with ``patient_id=None``.
    """

    merged_headers = _read_headers(headers)

    url = merged_headers.get(_FHIR_SERVER_URL_HEADER)
    token = merged_headers.get(_FHIR_ACCESS_TOKEN_HEADER)
    if not url or not token:
        return None

    patient_id = merged_headers.get(_PATIENT_ID_HEADER) or None
    session_id = merged_headers.get(_SESSION_ID_HEADER) or None
    issuer = merged_headers.get(_FHIR_ISSUER_HEADER) or None

    return SharpContext(
        url=url.rstrip("/"),
        token=token,
        patient_id=patient_id,
        session_id=session_id,
        issuer=issuer,
        raw_headers=dict(merged_headers),
    )


def require_sharp_context(
    headers: dict[str, str] | None = None,
    *,
    require_patient: bool = True,
) -> SharpContext:
    """Read SHARP context or raise ``SharpContextMissing``.

    Default behaviour (``require_patient=True``) insists on all three
    required headers + a patient id — use this from tools that read
    patient data from FHIR. Pass ``require_patient=False`` for tools
    that only need the FHIR server URL + token (e.g. terminology
    lookups against the FHIR server that don't touch a specific
    patient).
    """

    ctx = get_sharp_context(headers=headers)
    if ctx is None:
        raise SharpContextMissing(
            "SHARP context is required for this tool but no FHIR "
            f"server url and token were present. Expected headers: "
            f"{_FHIR_SERVER_URL_HEADER}, {_FHIR_ACCESS_TOKEN_HEADER}"
        )
    if require_patient and not ctx.has_patient:
        raise SharpContextMissing(
            "SHARP context is present but no patient id was supplied. "
            f"Expected header: {_PATIENT_ID_HEADER}"
        )
    return ctx


# ---------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------


def _read_headers(headers: dict[str, str] | None) -> dict[str, str]:
    """Return headers from the explicit arg when provided, else FastMCP.

    Header names are normalised to lowercase so callers can pass either
    ``"X-Fhir-Server-Url"`` or ``"x-fhir-server-url"`` (matches the
    HTTP case-insensitivity contract).
    """

    if headers is not None:
        return {k.lower(): v for k, v in headers.items()}

    # Late import — FastMCP's dependency utility is only available at
    # runtime when a request is in flight. During unit tests the
    # caller passes ``headers=`` explicitly; this branch is the
    # production path inside an MCP tool invocation.
    try:
        from fastmcp.server.dependencies import get_http_headers as _fastmcp_headers
    except ImportError:  # pragma: no cover — fastmcp is pinned in requirements
        return {}

    try:
        raw = _fastmcp_headers(include_all=True) or {}
    except Exception:  # pragma: no cover — absent outside a request
        return {}

    return {str(k).lower(): str(v) for k, v in raw.items()}


__all__ = [
    "SharpContext",
    "SharpContextMissing",
    "get_sharp_context",
    "require_sharp_context",
]


# ---------------------------------------------------------------------
# Provenance stamping helper
# ---------------------------------------------------------------------
#
# Kept separate from SharpContext so the dataclass stays pure-data.
# This is imported by the MCP tools that need to stamp a
# ProvenanceStamp (see ``integrations/mcp/models.py``) with SHARP
# session info.


def stamp_with_sharp(
    *,
    base: dict[str, Any] | None,
    ctx: SharpContext,
) -> dict[str, Any]:
    """Enrich an existing provenance stamp dict with SHARP fields.

    Returns a new dict; never mutates the input. Any of the SHARP
    session fields that are ``None`` are omitted rather than stamped
    as empty strings, so a downstream consumer can tell "no session"
    apart from "empty session".
    """

    stamp: dict[str, Any] = dict(base or {})
    stamp.setdefault("provenance_source", "prompt_opinion.sharp")
    stamp["sharp"] = {
        "fhir_server_url": ctx.url,
        "patient_id": ctx.patient_id,
        "session_id": ctx.session_id,
        "issuer": ctx.issuer,
    }
    # Strip nulls for a cleaner FHIR Provenance representation.
    stamp["sharp"] = {k: v for k, v in stamp["sharp"].items() if v is not None}
    return stamp
