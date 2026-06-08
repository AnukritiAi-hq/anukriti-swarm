"""T10 — unit tests for ``ai.narrative.llm_narrator.LLMNarrator``.

The narrator is the ONLY swarm seam that calls the LLM for user-facing
narrative. It must:

  * run offline with no client (returns an empty narrative — the
    byte-identical / no-network default),
  * accept any client exposing ``.generate(prompt) -> obj.text``,
  * validate the LLM output via ``CitationValidator``,
  * raise ``GenerativeBoundaryViolation`` when the model fabricates a
    citation (FABRICATE_CLAIM is a forbidden generative action).

All tests use a mock client — no real Gemini/OpenAI call is made.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from ai.narrative.llm_narrator import LLMNarrative, LLMNarrator
from core.orchestrator.boundary import GenerativeBoundaryViolation
from core.runtime.citation_validator import CitationVerdict


@dataclass
class _MockResponse:
    text: str
    model: str = "mock-gemini"


class _MockClient:
    """Minimal LLM client: returns a canned response from ``.generate``."""

    def __init__(self, text: str, model: str = "mock-gemini") -> None:
        self._text = text
        self._model = model
        self.calls: list[str] = []

    def generate(self, prompt: str) -> _MockResponse:
        self.calls.append(prompt)
        return _MockResponse(text=self._text, model=self._model)


_EVIDENCE = [
    {"source": "CPIC", "source_id": "PMID:35034351", "claim": "CYP2C19 PM clopidogrel guidance"},
    {"source": "PharmGKB", "source_id": "PA166104948", "claim": "SAS carrier frequency"},
]


# ---------------------------------------------------------------------------
# No-client / offline default
# ---------------------------------------------------------------------------


class TestNoClient:
    def test_no_client_returns_empty_narrative(self) -> None:
        narrator = LLMNarrator(client=None)
        result = narrator.narrate(
            gene="CYP2C19",
            drug="clopidogrel",
            population="SAS",
            phenotype="Poor Metabolizer",
            evidence_records=_EVIDENCE,
        )
        assert isinstance(result, LLMNarrative)
        assert result.text == ""
        assert result.model == "none"
        # Empty text -> EMPTY_RESPONSE verdict, not a crash.
        assert result.validation.verdict is CitationVerdict.EMPTY_RESPONSE


# ---------------------------------------------------------------------------
# Happy path — clean cited output
# ---------------------------------------------------------------------------


class TestCleanNarration:
    def test_fully_cited_output_validates_all_cited(self) -> None:
        text = (
            "CYP2C19 poor metabolizers cannot activate clopidogrel [CPIC, PMID:35034351]. "
            "South Asian carrier frequency is elevated [PharmGKB, PA166104948]."
        )
        narrator = LLMNarrator(client=_MockClient(text))
        result = narrator.narrate(
            gene="CYP2C19",
            drug="clopidogrel",
            population="SAS",
            phenotype="Poor Metabolizer",
            evidence_records=_EVIDENCE,
        )
        assert result.validation.verdict is CitationVerdict.ALL_CITED
        assert result.text == text
        assert result.model == "mock-gemini"
        # Citations extracted from the text.
        assert "[CPIC, PMID:35034351]" in result.citations

    def test_prompt_is_sent_to_client(self) -> None:
        client = _MockClient("All good [CPIC, PMID:35034351] for this whole sentence.")
        narrator = LLMNarrator(client=client)
        narrator.narrate(
            gene="CYP2C19",
            drug="clopidogrel",
            population="SAS",
            phenotype="Poor Metabolizer",
            evidence_records=_EVIDENCE,
        )
        assert len(client.calls) == 1
        # Grounding prompt always carries the frozen instruction.
        assert "Reason ONLY from the data below" in client.calls[0]


# ---------------------------------------------------------------------------
# Boundary — fabricated citation must raise
# ---------------------------------------------------------------------------


class TestFabricationBoundary:
    def test_fabricated_citation_raises_boundary_violation(self) -> None:
        # The model cites a source AND id that were never provided. The
        # validator treats a citation as fabricated only when neither the
        # source token, the id token, nor the combined token appears in the
        # evidence set — so we use a wholly invented source+id pair.
        text = "This recommendation rests on a fabricated source [FakeDB, XREF:00000000]."
        narrator = LLMNarrator(client=_MockClient(text))
        with pytest.raises(GenerativeBoundaryViolation):
            narrator.narrate(
                gene="CYP2C19",
                drug="clopidogrel",
                population="SAS",
                phenotype="Poor Metabolizer",
                evidence_records=_EVIDENCE,
            )


# ---------------------------------------------------------------------------
# Uncited output -> MISSING_CITATIONS (does not raise; surfaced in trace)
# ---------------------------------------------------------------------------


class TestUncitedNarration:
    def test_uncited_claim_surfaces_missing_citations(self) -> None:
        text = "Clopidogrel is completely safe for absolutely every patient everywhere."
        narrator = LLMNarrator(client=_MockClient(text))
        result = narrator.narrate(
            gene="CYP2C19",
            drug="clopidogrel",
            population="SAS",
            phenotype="Poor Metabolizer",
            evidence_records=_EVIDENCE,
        )
        assert result.validation.verdict is CitationVerdict.MISSING_CITATIONS
        assert len(result.validation.uncited_claims) >= 1
