"""Unit tests for ``hackathon.sharp.context``.

These do not require a running MCP server — they pass headers
explicitly to ``get_sharp_context()`` / ``require_sharp_context()``.
"""

from __future__ import annotations

import pytest

from hackathon.sharp import (
    SharpContext,
    SharpContextMissing,
    get_sharp_context,
    require_sharp_context,
    stamp_with_sharp,
)


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------


FULL_HEADERS = {
    "x-fhir-server-url": "https://fhir.example.org/r4",
    "x-fhir-access-token": "Bearer abc123",
    "x-patient-id": "patient-007",
    "x-session-id": "po-session-42",
    "x-fhir-issuer": "https://auth.example.org",
}

MINIMAL_HEADERS = {
    "x-fhir-server-url": "https://fhir.example.org/r4/",
    "x-fhir-access-token": "abc",
}

EMPTY_HEADERS: dict[str, str] = {}


# ---------------------------------------------------------------------
# get_sharp_context
# ---------------------------------------------------------------------


class TestGetSharpContext:
    def test_full_headers_returns_populated_context(self) -> None:
        ctx = get_sharp_context(headers=FULL_HEADERS)

        assert ctx is not None
        assert ctx.url == "https://fhir.example.org/r4"
        assert ctx.token == "Bearer abc123"
        assert ctx.patient_id == "patient-007"
        assert ctx.session_id == "po-session-42"
        assert ctx.issuer == "https://auth.example.org"
        assert ctx.has_patient is True

    def test_minimal_headers_returns_context_without_patient(self) -> None:
        ctx = get_sharp_context(headers=MINIMAL_HEADERS)

        assert ctx is not None
        # Trailing slash on input URL is stripped so downstream
        # joining with resource paths doesn't double-slash.
        assert ctx.url == "https://fhir.example.org/r4"
        assert ctx.patient_id is None
        assert ctx.session_id is None
        assert ctx.has_patient is False

    def test_empty_headers_returns_none(self) -> None:
        assert get_sharp_context(headers=EMPTY_HEADERS) is None

    def test_missing_token_returns_none(self) -> None:
        assert get_sharp_context(headers={"x-fhir-server-url": "https://x"}) is None

    def test_missing_url_returns_none(self) -> None:
        assert get_sharp_context(headers={"x-fhir-access-token": "abc"}) is None

    def test_case_insensitive_headers(self) -> None:
        mixed = {
            "X-Fhir-Server-Url": "https://fhir.example.org/r4",
            "X-FHIR-ACCESS-TOKEN": "tok",
            "X-Patient-Id": "p1",
        }
        ctx = get_sharp_context(headers=mixed)

        assert ctx is not None
        assert ctx.patient_id == "p1"

    def test_raw_headers_preserved(self) -> None:
        ctx = get_sharp_context(headers=FULL_HEADERS)

        assert ctx is not None
        # Names stored lowercase so downstream code has one source
        # of truth; values unchanged.
        assert ctx.raw_headers["x-fhir-server-url"] == "https://fhir.example.org/r4"
        assert ctx.raw_headers["x-session-id"] == "po-session-42"

    def test_context_is_frozen(self) -> None:
        ctx = get_sharp_context(headers=FULL_HEADERS)

        assert ctx is not None
        with pytest.raises(Exception):
            ctx.patient_id = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------
# require_sharp_context
# ---------------------------------------------------------------------


class TestRequireSharpContext:
    def test_full_headers_returns_context(self) -> None:
        ctx = require_sharp_context(headers=FULL_HEADERS)

        assert ctx.patient_id == "patient-007"

    def test_empty_headers_raises(self) -> None:
        with pytest.raises(SharpContextMissing):
            require_sharp_context(headers=EMPTY_HEADERS)

    def test_missing_patient_raises_when_required(self) -> None:
        with pytest.raises(SharpContextMissing, match="patient"):
            require_sharp_context(headers=MINIMAL_HEADERS, require_patient=True)

    def test_missing_patient_allowed_when_not_required(self) -> None:
        ctx = require_sharp_context(headers=MINIMAL_HEADERS, require_patient=False)

        assert ctx.patient_id is None


# ---------------------------------------------------------------------
# Provenance stamping
# ---------------------------------------------------------------------


class TestStampWithSharp:
    def test_adds_sharp_block_to_stamp(self) -> None:
        ctx = get_sharp_context(headers=FULL_HEADERS)
        assert ctx is not None

        stamp = stamp_with_sharp(base={"source_id": "CPIC:2022"}, ctx=ctx)

        assert stamp["source_id"] == "CPIC:2022"
        assert stamp["provenance_source"] == "prompt_opinion.sharp"
        assert stamp["sharp"]["patient_id"] == "patient-007"
        assert stamp["sharp"]["session_id"] == "po-session-42"

    def test_strips_none_fields(self) -> None:
        ctx = get_sharp_context(headers=MINIMAL_HEADERS)
        assert ctx is not None

        stamp = stamp_with_sharp(base=None, ctx=ctx)

        # session_id and patient_id and issuer are None — should
        # be omitted, not stamped as empty.
        assert "patient_id" not in stamp["sharp"]
        assert "session_id" not in stamp["sharp"]
        assert "issuer" not in stamp["sharp"]
        assert stamp["sharp"]["fhir_server_url"] == "https://fhir.example.org/r4"

    def test_does_not_mutate_base(self) -> None:
        base = {"source_id": "original"}
        ctx = get_sharp_context(headers=FULL_HEADERS)
        assert ctx is not None

        stamp_with_sharp(base=base, ctx=ctx)

        assert base == {"source_id": "original"}


# ---------------------------------------------------------------------
# provenance_agent_id
# ---------------------------------------------------------------------


class TestProvenanceAgentId:
    def test_full_context_encodes_session_and_patient(self) -> None:
        ctx = get_sharp_context(headers=FULL_HEADERS)
        assert ctx is not None

        agent_id = ctx.provenance_agent_id()

        assert "po-session-42" in agent_id
        assert "patient-007" in agent_id
        assert agent_id.startswith("anukriti-pgx:")

    def test_minimal_context_uses_placeholders(self) -> None:
        ctx = get_sharp_context(headers=MINIMAL_HEADERS)
        assert ctx is not None

        agent_id = ctx.provenance_agent_id()

        assert "session-unknown" in agent_id
        assert "no-patient" in agent_id


def test_sharp_context_dataclass_is_importable() -> None:
    """Ensure SharpContext itself can be constructed directly.

    This keeps the type public for downstream callers (tests, demo,
    tooling) that want to build one without going through a request.
    """
    ctx = SharpContext(
        url="https://fhir.example.org",
        token="tok",
        patient_id="p1",
    )
    assert ctx.has_patient is True
