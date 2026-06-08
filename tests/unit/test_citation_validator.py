"""T10 — unit tests for ``core.runtime.citation_validator.CitationValidator``.

The validator enforces the C1..C5 named-refusal taxonomy:

    C1  uncited factual claim       -> MISSING_CITATIONS
    C2  citation not in record set  -> FABRICATED_CITATION
    C3  empty response              -> EMPTY_RESPONSE
    C4  malformed citation token    -> MALFORMED (currently surfaced as C1
                                       when the token does not parse at all)
    C5  all claims cited            -> ALL_CITED

Each test pins one rule firing on the right input. These are pure unit
tests (no LLM, no network) and run in milliseconds.
"""

from __future__ import annotations

from core.runtime.citation_validator import (
    CitationRule,
    CitationValidator,
    CitationVerdict,
)


def _validator() -> CitationValidator:
    return CitationValidator()


# ---------------------------------------------------------------------------
# C5 — all clean
# ---------------------------------------------------------------------------


class TestC5AllCited:
    def test_single_cited_claim_is_all_cited(self) -> None:
        text = "CYP2C19 *2/*2 is a loss-of-function genotype [CPIC, PMID:35034351]."
        trace = _validator().validate(text, {"PMID:35034351"})
        assert trace.verdict is CitationVerdict.ALL_CITED
        assert CitationRule.C5 in trace.rules_triggered
        assert trace.uncited_claims == ()
        assert trace.fabricated_citations == ()

    def test_multiple_cited_claims_all_clean(self) -> None:
        text = (
            "Clopidogrel requires CYP2C19 activation [CPIC, PMID:35034351]. "
            "South Asian carrier frequency is elevated [PharmGKB, PA166104948]."
        )
        ids = {"PMID:35034351", "PA166104948"}
        trace = _validator().validate(text, ids)
        assert trace.verdict is CitationVerdict.ALL_CITED
        assert trace.cited_sentences >= 2

    def test_no_record_set_only_requires_token_present(self) -> None:
        # When evidence_source_ids is None, the validator only checks that
        # citation tokens exist — it cannot verify them against a set.
        text = "This claim carries a citation token of some kind [CPIC, PMID:1]."
        trace = _validator().validate(text, None)
        assert trace.verdict is CitationVerdict.ALL_CITED


# ---------------------------------------------------------------------------
# C1 — uncited claim
# ---------------------------------------------------------------------------


class TestC1MissingCitations:
    def test_uncited_claim_is_missing_citations(self) -> None:
        text = "Clopidogrel is completely safe for every single patient population."
        trace = _validator().validate(text, {"PMID:35034351"})
        assert trace.verdict is CitationVerdict.MISSING_CITATIONS
        assert CitationRule.C1 in trace.rules_triggered
        assert len(trace.uncited_claims) == 1

    def test_one_cited_one_uncited_is_missing_citations(self) -> None:
        text = (
            "CYP2C19 *2/*2 reduces clopidogrel activation [CPIC, PMID:35034351]. "
            "Therefore this patient will absolutely have a second cardiac event."
        )
        trace = _validator().validate(text, {"PMID:35034351"})
        assert trace.verdict is CitationVerdict.MISSING_CITATIONS
        assert len(trace.uncited_claims) == 1


# ---------------------------------------------------------------------------
# C2 — fabricated citation (not in the provided record set)
# ---------------------------------------------------------------------------


class TestC2FabricatedCitation:
    def test_citation_not_in_record_set_is_fabricated(self) -> None:
        text = "This claim cites a source that was never provided [CPIC, PMID:99999999]."
        trace = _validator().validate(text, {"PMID:35034351"})
        assert trace.verdict is CitationVerdict.FABRICATED_CITATION
        assert CitationRule.C2 in trace.rules_triggered
        assert "[CPIC, PMID:99999999]" in trace.fabricated_citations

    def test_fabrication_wins_over_missing(self) -> None:
        # A run with both an uncited claim and a fabricated citation reports
        # the more severe FABRICATED_CITATION verdict.
        text = (
            "This is an uncited assertion about drug safety in everyone. "
            "And this one cites a fake source [CPIC, PMID:00000000]."
        )
        trace = _validator().validate(text, {"PMID:35034351"})
        assert trace.verdict is CitationVerdict.FABRICATED_CITATION


# ---------------------------------------------------------------------------
# C3 — empty response
# ---------------------------------------------------------------------------


class TestC3EmptyResponse:
    def test_empty_string_is_empty_response(self) -> None:
        trace = _validator().validate("", {"PMID:1"})
        assert trace.verdict is CitationVerdict.EMPTY_RESPONSE
        assert trace.rules_triggered == (CitationRule.C3,)
        assert trace.total_sentences == 0

    def test_whitespace_only_is_empty_response(self) -> None:
        trace = _validator().validate("   \n\t  ", {"PMID:1"})
        assert trace.verdict is CitationVerdict.EMPTY_RESPONSE


# ---------------------------------------------------------------------------
# Structural sentences are skipped (headers / short transitional lines)
# ---------------------------------------------------------------------------


class TestStructuralSkips:
    def test_header_and_short_lines_do_not_count_as_uncited(self) -> None:
        text = (
            "In summary: the evidence is clear. "
            "CYP2C19 *2/*2 reduces activation [CPIC, PMID:35034351]."
        )
        trace = _validator().validate(text, {"PMID:35034351"})
        assert trace.verdict is CitationVerdict.ALL_CITED


# ---------------------------------------------------------------------------
# Trace shape — auditable record
# ---------------------------------------------------------------------------


class TestTraceShape:
    def test_trace_carries_per_sentence_validation(self) -> None:
        text = (
            "CYP2C19 *2/*2 reduces clopidogrel activation [CPIC, PMID:35034351]. "
            "This patient will surely have an adverse outcome no matter what."
        )
        trace = _validator().validate(text, {"PMID:35034351"})
        assert trace.total_sentences == 2
        # exactly one valid (cited) and one invalid (uncited) sentence
        valid = [s for s in trace.sentences if s.is_valid]
        invalid = [s for s in trace.sentences if not s.is_valid]
        assert len(valid) == 1
        assert len(invalid) == 1
        assert invalid[0].rule is CitationRule.C1
