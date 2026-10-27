"""Unit tests for rule C6 — the numeric-drift guard in CitationValidator.

C6 catches what a citation check structurally cannot see: a sentence that
is perfectly cited and still states a number the grounded context never
contained. The tests that matter most are the ones asserting it does
*not* fire, because a guard that rejects correct genomic notation or a
legitimate dose gets switched off.

Pure unit tests, no LLM, no network.
"""

from __future__ import annotations

import pytest

from core.runtime.citation_validator import (
    CitationRule,
    CitationValidator,
    CitationVerdict,
    unsupported_quantities,
)

CONTEXT = (
    "CPIC Recommendations:\n"
    "  - [Strong] Reduce fluorouracil starting dose by 50% in DPYD "
    "intermediate metabolizers.\n"
    "Evidence Records:\n"
    "  [CPIC, PMID:29152729]: Standard capecitabine dosing is 1250 mg/m2 "
    "twice daily.\n"
)


def _validator() -> CitationValidator:
    return CitationValidator()


# ---------------------------------------------------------------------------
# C6 fires
# ---------------------------------------------------------------------------


class TestC6Fires:
    def test_cited_sentence_with_a_drifted_dose_is_rejected(self) -> None:
        text = "Reduce the fluorouracil starting dose by 40% [CPIC, PMID:29152729]."
        trace = _validator().validate(
            text, {"PMID:29152729"}, grounded_context=CONTEXT
        )
        assert trace.verdict is CitationVerdict.UNSUPPORTED_QUANTITY
        assert CitationRule.C6 in trace.rules_triggered
        assert trace.unsupported_quantities == ("40%",)
        # The citation itself was fine — this is the gap C2 cannot see.
        assert trace.fabricated_citations == ()

    def test_short_sentence_is_still_checked(self) -> None:
        """"Reduce by 40%." is 14 chars and skips the citation rules."""
        trace = _validator().validate(
            "Reduce by 40%.", {"PMID:29152729"}, grounded_context=CONTEXT
        )
        assert trace.verdict is CitationVerdict.UNSUPPORTED_QUANTITY
        assert trace.unsupported_quantities == ("40%",)

    def test_invented_body_surface_dose_is_rejected(self) -> None:
        text = "Give capecitabine 625 mg/m2 twice daily [CPIC, PMID:29152729]."
        trace = _validator().validate(
            text, {"PMID:29152729"}, grounded_context=CONTEXT
        )
        assert trace.unsupported_quantities == ("625 mg/m2",)

    def test_quantity_outranks_a_missing_citation(self) -> None:
        text = "Reduce the fluorouracil starting dose by 40% in these patients."
        trace = _validator().validate(
            text, {"PMID:29152729"}, grounded_context=CONTEXT
        )
        assert trace.verdict is CitationVerdict.UNSUPPORTED_QUANTITY
        assert CitationRule.C1 in trace.rules_triggered

    def test_fabricated_citation_still_outranks_a_quantity(self) -> None:
        text = "Reduce the dose by 40% [CPIC, PMID:99999999]."
        trace = _validator().validate(
            text, {"PMID:29152729"}, grounded_context=CONTEXT
        )
        assert trace.verdict is CitationVerdict.FABRICATED_CITATION
        assert trace.unsupported_quantities == ("40%",)


# ---------------------------------------------------------------------------
# C6 stays silent
# ---------------------------------------------------------------------------


class TestC6StaysSilent:
    def test_matching_dose_passes(self) -> None:
        text = "Reduce the fluorouracil starting dose by 50% [CPIC, PMID:29152729]."
        trace = _validator().validate(
            text, {"PMID:29152729"}, grounded_context=CONTEXT
        )
        assert trace.verdict is CitationVerdict.ALL_CITED
        assert trace.unsupported_quantities == ()

    def test_rule_does_not_run_without_a_context(self) -> None:
        """An unverifiable quantity is not a wrong one."""
        text = "Reduce the fluorouracil starting dose by 40% [CPIC, PMID:29152729]."
        trace = _validator().validate(text, {"PMID:29152729"})
        assert trace.verdict is CitationVerdict.ALL_CITED
        assert trace.unsupported_quantities == ()

    @pytest.mark.parametrize(
        "sentence",
        [
            "The defining variant is c.1905+1G>A in DPYD [CPIC, PMID:29152729].",
            "Variant rs3918290 was detected in this sample [CPIC, PMID:29152729].",
            "Reference build GRCh38 was used throughout [CPIC, PMID:29152729].",
            "The guideline is PMID 29152729 [CPIC, PMID:29152729].",
            "The DPYD activity score is 1.5 here [CPIC, PMID:29152729].",
            "Position chr1:97450058 was covered [CPIC, PMID:29152729].",
        ],
    )
    def test_identifiers_are_not_quantities(self, sentence: str) -> None:
        trace = _validator().validate(
            sentence, {"PMID:29152729"}, grounded_context=CONTEXT
        )
        assert trace.unsupported_quantities == (), sentence
        assert trace.verdict is CitationVerdict.ALL_CITED


# ---------------------------------------------------------------------------
# The helper directly
# ---------------------------------------------------------------------------


class TestUnsupportedQuantitiesHelper:
    def test_value_present_with_a_different_unit_is_accepted(self) -> None:
        """Units often sit in a field name, not beside the number."""
        assert unsupported_quantities("Reduce by 50%.", "dose_reduction_percent: 50") == ()

    def test_normalises_decimal_spelling(self) -> None:
        assert unsupported_quantities("Give 1.50 mg daily.", "dose is 1.5 mg") == ()

    def test_reports_each_bad_quantity_once(self) -> None:
        flagged = unsupported_quantities("40% now and 40% later.", "use 50%")
        assert flagged == ("40%",)

    def test_empty_inputs_are_safe(self) -> None:
        assert unsupported_quantities("", "") == ()
        assert unsupported_quantities("Reduce by 40%.", "") == ("40%",)


# ---------------------------------------------------------------------------
# Wiring: the narrator must hand the validator the context it used
# ---------------------------------------------------------------------------


class TestNarratorPassesGroundedContext:
    """C6 is inert unless the caller supplies the context block."""

    @staticmethod
    def _narrate(text: str):
        from dataclasses import dataclass

        from ai.narrative.llm_narrator import LLMNarrator

        @dataclass
        class _Resp:
            text: str
            model: str = "mock"

        class _Client:
            def generate(self, prompt: str) -> _Resp:
                return _Resp(text=text)

        narrator = LLMNarrator(client=_Client(), audience="clinician")
        return narrator.narrate(
            gene="DPYD",
            drug="fluorouracil",
            population="SAS",
            phenotype="Intermediate Metabolizer",
            evidence_records=[
                {
                    "source": "CPIC",
                    "source_id": "PMID:29152729",
                    "claim": "Reduce the fluorouracil starting dose by 50%.",
                }
            ],
        )

    def test_drifted_dose_is_caught_through_the_narrator(self) -> None:
        result = self._narrate(
            "Reduce the fluorouracil starting dose by 40% [CPIC, PMID:29152729]."
        )
        assert result.validation.verdict is CitationVerdict.UNSUPPORTED_QUANTITY
        assert result.validation.unsupported_quantities == ("40%",)

    def test_matching_dose_passes_through_the_narrator(self) -> None:
        result = self._narrate(
            "Reduce the fluorouracil starting dose by 50% [CPIC, PMID:29152729]."
        )
        assert result.validation.verdict is CitationVerdict.ALL_CITED
        assert result.validation.unsupported_quantities == ()
