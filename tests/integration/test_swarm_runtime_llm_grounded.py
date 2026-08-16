"""T10 — integration tests for ``SwarmRuntime`` ``synthesis_mode``.

These exercise the opt-in LLM-grounded Stage-5b path end-to-end and,
critically, pin the **byte-identical regression contract**: a runtime
with default ``synthesis_mode`` (None / "template") must produce exactly
the same deterministic output as before the grounded path existed.

The grounded path is driven by an injected mock narrator so no real
Gemini/OpenAI call happens here.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.models.population import SuperPopulation
from core.runtime.context import UnifiedExecutionContext
from core.runtime.events import InMemoryEventStream, RuntimeEventKind
from core.runtime.runtime import SwarmRuntime

# ---------------------------------------------------------------------------
# Mock narrator: returns a canned LLMNarrative without any LLM call.
# ---------------------------------------------------------------------------


@dataclass
class _StubValidation:
    verdict: object
    total_sentences: int = 1
    cited_sentences: int = 1
    uncited_claims: tuple = ()
    fabricated_citations: tuple = ()
    rules_triggered: tuple = ()


@dataclass
class _StubNarrative:
    text: str
    citations: tuple
    validation: _StubValidation
    chemistry_context: dict
    model: str = "mock-gemini"
    latency_ms: float = 1.0


class _MockNarrator:
    """Stands in for LLMNarrator; emits a chosen validation verdict."""

    def __init__(self, text: str, verdict: object, citations: tuple = ()) -> None:
        self._text = text
        self._verdict = verdict
        self._citations = citations

    def narrate(self, **_kwargs) -> _StubNarrative:
        from core.runtime.citation_validator import CitationRule

        return _StubNarrative(
            text=self._text,
            citations=self._citations,
            validation=_StubValidation(
                verdict=self._verdict,
                uncited_claims=("an uncited claim",)
                if self._verdict.name == "MISSING_CITATIONS"
                else (),
                rules_triggered=(CitationRule.C5,),
            ),
            chemistry_context={"drug": "clopidogrel"},
        )


def _sas_clopidogrel() -> UnifiedExecutionContext:
    return UnifiedExecutionContext.new(
        drug="clopidogrel",
        gene="CYP2C19",
        population=SuperPopulation.SAS,
        genotype="*2/*2",
    )


# ---------------------------------------------------------------------------
# Byte-identical regression: default mode unchanged
# ---------------------------------------------------------------------------


class TestTemplateModeRegression:
    def test_default_mode_has_no_grounded_narrative(self) -> None:
        report = SwarmRuntime(event_stream=InMemoryEventStream()).run(_sas_clopidogrel())
        assert report.grounded_narrative is None

    def test_template_string_mode_has_no_grounded_narrative(self) -> None:
        report = SwarmRuntime(event_stream=InMemoryEventStream(), synthesis_mode="template").run(
            _sas_clopidogrel()
        )
        assert report.grounded_narrative is None

    def test_default_vs_template_recommendation_identical(self) -> None:
        r_default = SwarmRuntime(event_stream=InMemoryEventStream()).run(_sas_clopidogrel())
        r_template = SwarmRuntime(
            event_stream=InMemoryEventStream(), synthesis_mode="template"
        ).run(_sas_clopidogrel())
        # The deterministic recommendation must be byte-identical.
        assert r_default.final_recommendation["text"] == r_template.final_recommendation["text"]
        assert r_default.deterministic_rules == r_template.deterministic_rules


# ---------------------------------------------------------------------------
# Grounded mode — clean (ALL_CITED) attaches the narrative
# ---------------------------------------------------------------------------


class TestGroundedModeClean:
    def test_all_cited_attaches_grounded_narrative(self) -> None:
        from core.runtime.citation_validator import CitationVerdict

        text = "CYP2C19 PM cannot activate clopidogrel [CPIC, PMID:35034351]."
        runtime = SwarmRuntime(
            event_stream=InMemoryEventStream(),
            synthesis_mode="llm_grounded",
            llm_narrator=_MockNarrator(
                text, CitationVerdict.ALL_CITED, citations=("[CPIC, PMID:35034351]",)
            ),
        )
        report = runtime.run(_sas_clopidogrel())
        assert report.grounded_narrative is not None
        assert report.grounded_narrative["text"] == text
        assert report.grounded_narrative["used_fallback"] is False
        # Deterministic recommendation is still the authoritative output.
        assert report.final_recommendation["allows_synthesis"] is True
        assert "clopidogrel" in report.final_recommendation["text"].lower()


# ---------------------------------------------------------------------------
# Grounded mode — validation failure falls back with a named C-rule
# ---------------------------------------------------------------------------


class TestGroundedModeFallback:
    def test_missing_citations_drops_text_and_names_c1(self) -> None:
        from core.runtime.citation_validator import CitationVerdict

        bad_text = "Clopidogrel is safe for everyone with no exceptions whatsoever."
        runtime = SwarmRuntime(
            event_stream=InMemoryEventStream(),
            synthesis_mode="llm_grounded",
            llm_narrator=_MockNarrator(bad_text, CitationVerdict.MISSING_CITATIONS),
        )
        report = runtime.run(_sas_clopidogrel())
        grounded = report.grounded_narrative
        assert grounded is not None
        # Unvalidated text is dropped from the user-facing slot...
        assert grounded["text"] == ""
        # ...but preserved in the trace for audit, with the named rule.
        assert grounded["used_fallback"] is True
        assert grounded["fallback_rule"] == "C1"
        assert grounded["fallback_to"] == "deterministic"
        assert grounded["unvalidated_text"] == bad_text
        # The deterministic recommendation is untouched.
        assert report.final_recommendation["allows_synthesis"] is True

    def test_fallback_emits_safe_abstention_for_grounded(self) -> None:
        from core.runtime.citation_validator import CitationVerdict

        runtime = SwarmRuntime(
            event_stream=InMemoryEventStream(),
            synthesis_mode="llm_grounded",
            llm_narrator=_MockNarrator("uncited text here", CitationVerdict.FABRICATED_CITATION),
        )
        runtime.run(_sas_clopidogrel())
        assert isinstance(runtime.event_stream, InMemoryEventStream)
        grounded_abstentions = [
            e
            for e in runtime.event_stream.events
            if e.kind is RuntimeEventKind.SAFE_ABSTENTION and e.payload.get("grounded")
        ]
        assert grounded_abstentions
        assert grounded_abstentions[0].payload["rule"] == "C2"


# ---------------------------------------------------------------------------
# Grounded mode does not run when sufficiency blocks synthesis
# ---------------------------------------------------------------------------


class TestGroundedModeRespectsAbstention:
    def test_no_grounded_narrative_when_synthesis_blocked(self) -> None:
        from core.runtime.citation_validator import CitationVerdict

        # AFR + codeine is an honest refusal in the seed KG (no synthesis).
        ctx = UnifiedExecutionContext.new(
            drug="codeine",
            gene="CYP2D6",
            population=SuperPopulation.AFR,
            genotype="*4/*4",
        )
        runtime = SwarmRuntime(
            event_stream=InMemoryEventStream(),
            synthesis_mode="llm_grounded",
            llm_narrator=_MockNarrator("should never run", CitationVerdict.ALL_CITED),
        )
        report = runtime.run(ctx)
        assert report.final_recommendation["allows_synthesis"] is False
        # Stage 5b is gated behind the deterministic synthesis gate.
        assert report.grounded_narrative is None
