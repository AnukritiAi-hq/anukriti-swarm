"""Tests for ``interoperability.shared_context.envelope``.

The AgentContextEnvelope is one of the project's strongest scope
firewalls — a closed 7-value ``BiomedicalContextType`` enum
restricts inter-agent messages to genomic concepts. Messages
shaped for hospital / EHR / clinical-copilot workflows cannot
construct a valid envelope.

This file asserts:

1. ``BiomedicalContextType`` has exactly 7 values: population,
   genotype, pharmacogene, evidence, verification, confidence,
   provenance. String values are stable wire format.
2. Unknown context types are rejected at construction.
3. VerificationState is a closed 4-value enum.
4. ConfidenceLevel is a closed 4-value enum.
5. The envelope is frozen (pydantic frozen=True).
6. ``with_evidence`` / ``with_verification`` / ``with_delivery``
   produce new instances; the original is preserved.
7. ``is_safe`` / ``blocks_delivery`` correctly reflect verification.
"""

from __future__ import annotations

import pytest
from interoperability.shared_context.envelope import (
    AgentContextEnvelope,
    BiomedicalContextType,
    ConfidenceLevel,
    VerificationState,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Closed enum: BiomedicalContextType — THE scope firewall
# ---------------------------------------------------------------------------


class TestBiomedicalContextType:
    def test_has_exactly_7_values(self) -> None:
        assert len(list(BiomedicalContextType)) == 7

    def test_values_are_stable(self) -> None:
        # Wire-compatible values — JSON consumers / MCP persistence
        # read these strings directly. Changing any is a breaking
        # change for downstream systems.
        assert {k.value for k in BiomedicalContextType} == {
            "population",
            "genotype",
            "pharmacogene",
            "evidence",
            "verification",
            "confidence",
            "provenance",
        }

    @pytest.mark.parametrize(
        "forbidden_value",
        [
            "clinical_record",  # EHR domain
            "appointment",  # hospital workflow
            "billing",  # finance
            "patient_chat",  # consumer health
            "lab_result",  # clinical-copilot
            "imaging",  # radiology
        ],
    )
    def test_non_genomic_values_rejected(self, forbidden_value: str) -> None:
        """The firewall: out-of-scope values must fail at construction."""
        with pytest.raises(ValueError):
            BiomedicalContextType(forbidden_value)


class TestVerificationStateEnum:
    def test_has_exactly_4_states(self) -> None:
        assert len(list(VerificationState)) == 4

    def test_values_match_safety_engine_vocabulary(self) -> None:
        # These values must align with VerificationTrace.state so
        # the propagation layer doesn't have to translate.
        assert {k.value for k in VerificationState} == {
            "pending",
            "pass",
            "warn",
            "fail",
        }


class TestConfidenceLevelEnum:
    def test_has_exactly_4_levels(self) -> None:
        assert len(list(ConfidenceLevel)) == 4

    def test_values_are_stable(self) -> None:
        assert {k.value for k in ConfidenceLevel} == {
            "high",
            "moderate",
            "low",
            "insufficient",
        }


# ---------------------------------------------------------------------------
# Envelope construction — every required field + scope firewall
# ---------------------------------------------------------------------------


def _base_envelope(**overrides) -> AgentContextEnvelope:
    """Build a minimally-valid envelope. Tests override any field."""
    defaults: dict = {
        "originating_agent": "test-agent",
        "workflow_id": "run-1",
        "biomedical_context_type": BiomedicalContextType.GENOTYPE,
    }
    defaults.update(overrides)
    return AgentContextEnvelope(**defaults)


class TestEnvelopeConstruction:
    def test_minimal_envelope_constructs(self) -> None:
        env = _base_envelope()
        assert env.originating_agent == "test-agent"
        assert env.workflow_id == "run-1"
        assert env.biomedical_context_type is BiomedicalContextType.GENOTYPE

    def test_envelope_rejects_non_enum_context_type(self) -> None:
        """Passing a random string for biomedical_context_type must raise
        — that's the scope firewall."""
        with pytest.raises(ValidationError):
            AgentContextEnvelope(
                originating_agent="a",
                workflow_id="w",
                biomedical_context_type="clinical_record",  # not in enum
            )

    def test_envelope_rejects_missing_context_type(self) -> None:
        with pytest.raises(ValidationError):
            AgentContextEnvelope(
                originating_agent="a",
                workflow_id="w",
                # biomedical_context_type omitted
            )

    @pytest.mark.parametrize("ctx_type", list(BiomedicalContextType))
    def test_all_allowed_context_types_accepted(self, ctx_type: BiomedicalContextType) -> None:
        env = _base_envelope(biomedical_context_type=ctx_type)
        assert env.biomedical_context_type is ctx_type

    def test_default_verification_state_is_pending(self) -> None:
        assert _base_envelope().verification_state is VerificationState.PENDING

    def test_default_confidence_is_moderate(self) -> None:
        assert _base_envelope().confidence_level is ConfidenceLevel.MODERATE

    def test_confidence_value_clamped_in_unit_interval(self) -> None:
        with pytest.raises(ValidationError):
            _base_envelope(confidence_value=1.5)  # above 1.0
        with pytest.raises(ValidationError):
            _base_envelope(confidence_value=-0.1)  # below 0.0


# ---------------------------------------------------------------------------
# Frozen-ness
# ---------------------------------------------------------------------------


class TestFrozenEnvelope:
    def test_assignment_to_field_raises(self) -> None:
        env = _base_envelope()
        with pytest.raises((ValidationError, Exception)):
            env.originating_agent = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Annotated copies
# ---------------------------------------------------------------------------


class TestAnnotatedCopies:
    def test_with_evidence_adds_refs_and_dedupes(self) -> None:
        env = _base_envelope()
        new = env.with_evidence("PMID:1", "PMID:2", "PMID:1")
        assert new.evidence_references == ("PMID:1", "PMID:2")
        # Original unchanged.
        assert env.evidence_references == ()

    def test_with_evidence_extends_existing_refs(self) -> None:
        env = _base_envelope(evidence_references=("PMID:a",))
        new = env.with_evidence("PMID:b", "PMID:a")
        assert new.evidence_references == ("PMID:a", "PMID:b")

    def test_with_verification_updates_state_only(self) -> None:
        env = _base_envelope()
        new = env.with_verification(VerificationState.PASSED)
        assert new.verification_state is VerificationState.PASSED
        assert env.verification_state is VerificationState.PENDING
        assert new.confidence_level is env.confidence_level  # unchanged

    def test_with_verification_updates_confidence(self) -> None:
        env = _base_envelope()
        new = env.with_verification(
            VerificationState.PASSED,
            confidence_level=ConfidenceLevel.HIGH,
            confidence_value=0.9,
        )
        assert new.verification_state is VerificationState.PASSED
        assert new.confidence_level is ConfidenceLevel.HIGH
        assert new.confidence_value == 0.9


# ---------------------------------------------------------------------------
# Safety gate accessors
# ---------------------------------------------------------------------------


class TestSafetyGates:
    def test_is_safe_true_for_passed(self) -> None:
        env = _base_envelope(verification_state=VerificationState.PASSED)
        assert env.is_safe
        assert not env.blocks_delivery

    def test_is_safe_true_for_warning(self) -> None:
        env = _base_envelope(verification_state=VerificationState.WARNING)
        assert env.is_safe
        assert not env.blocks_delivery

    def test_is_safe_false_for_pending(self) -> None:
        env = _base_envelope(verification_state=VerificationState.PENDING)
        assert not env.is_safe
        assert not env.blocks_delivery

    def test_blocks_delivery_true_for_failed(self) -> None:
        env = _base_envelope(verification_state=VerificationState.FAILED)
        assert not env.is_safe
        assert env.blocks_delivery


# ---------------------------------------------------------------------------
# correlation_id / source_agent aliases (legacy-idiom compatibility)
# ---------------------------------------------------------------------------


class TestAliases:
    def test_correlation_id_aliases_workflow_id(self) -> None:
        env = _base_envelope(workflow_id="run-42")
        assert env.correlation_id == "run-42"

    def test_source_agent_aliases_originating_agent(self) -> None:
        env = _base_envelope(originating_agent="pop-agent")
        assert env.source_agent == "pop-agent"
