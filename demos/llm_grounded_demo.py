"""Anukriti Swarm — LLM-Grounded Synthesis Demo (T11).

Demonstrates the opt-in ``synthesis_mode="llm_grounded"`` Stage-5b path
and, crucially, its **named-refusal fallback contract**:

    The deterministic narrative is ALWAYS the authoritative output.
    The LLM narrative is an additive adornment that only survives when
    it passes the CitationValidator. A fabricated citation fires the
    C2 rule, the unvalidated LLM text is dropped from the user-facing
    slot (kept in the trace for audit), and the run falls back to the
    deterministic narrative — without crashing.

Three acts, all offline (no real Gemini/OpenAI call):

  ACT 1  clean cited LLM output           -> ALL_CITED, grounded narrative attached
  ACT 2  fabricated-citation LLM output   -> C2 refusal, fallback to deterministic
  ACT 3  uncited-claim LLM output         -> C1 refusal, fallback to deterministic

Run: python -m demos.llm_grounded_demo
"""

from __future__ import annotations

from dataclasses import dataclass

from ai.narrative.llm_narrator import LLMNarrator
from core.models.population import SuperPopulation
from core.runtime.context import UnifiedExecutionContext
from core.runtime.events import InMemoryEventStream
from core.runtime.runtime import SwarmRuntime

# ---------------------------------------------------------------------------
# Offline mock LLM client — returns a canned response. No network call.
# ---------------------------------------------------------------------------


@dataclass
class _MockResponse:
    text: str
    model: str = "mock-gemini-2.5-flash"


class _MockClient:
    """Stands in for a real Gemini/OpenAI client."""

    def __init__(self, text: str) -> None:
        self._text = text

    def generate(self, prompt: str) -> _MockResponse:  # — prompt unused in mock
        return _MockResponse(text=self._text)


def _sas_clopidogrel() -> UnifiedExecutionContext:
    return UnifiedExecutionContext.new(
        drug="clopidogrel",
        gene="CYP2C19",
        population=SuperPopulation.SAS,
        genotype="*2/*2",
    )


def _run_act(title: str, subtitle: str, llm_text: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {title}")
    print(f"  {subtitle}")
    print("=" * 70)

    runtime = SwarmRuntime(
        event_stream=InMemoryEventStream(),
        synthesis_mode="llm_grounded",
        llm_narrator=LLMNarrator(client=_MockClient(llm_text), audience="clinician"),
    )
    report = runtime.run(_sas_clopidogrel())

    # Authoritative deterministic output (always present when synthesis allowed).
    det = report.final_recommendation
    print(f"\n  LLM draft text:\n    {llm_text}")
    print("\n  Deterministic (authoritative) recommendation:")
    print(f"    {det['text'][:200]}")

    grounded = report.grounded_narrative or {}
    verdict = grounded.get("validation", {}).get("verdict", "n/a")
    print(f"\n  Citation verdict: {verdict}")

    if grounded.get("used_fallback"):
        rule = grounded.get("fallback_rule", "?")
        print(f"  ⚠️  NAMED REFUSAL [{rule}] — unvalidated LLM text DROPPED from output.")
        print(f"      Fallback to: {grounded.get('fallback_to')}")
        print("      (Unvalidated text preserved in trace for audit:)")
        print(f"        {grounded.get('unvalidated_text', '')[:120]}")
        print(f"      User-facing grounded text is now empty: {grounded.get('text', '') == ''}")
    else:
        print("  ✅ ALL_CITED — grounded narrative attached:")
        print(f"      {grounded.get('text', '')[:200]}")

    # The deterministic recommendation is untouched in every case.
    assert det["allows_synthesis"] is True
    assert "clopidogrel" in det["text"].lower()


def run_demo() -> None:
    print("=" * 70)
    print("🧬 ANUKRITI SWARM — LLM-Grounded Synthesis Demo (T9/T11)")
    print("   'The LLM explains; deterministic rules decide.'")
    print("   synthesis_mode='llm_grounded' is OFF by default and additive.")
    print("=" * 70)

    # ACT 1 — clean cited output. The citation id must match one of the
    # ids actually retrieved for this run (the SAS/clopidogrel retrieval
    # returns PMID:34032273 and PA166169660), otherwise the validator
    # correctly flags it as fabricated relative to the real evidence set.
    _run_act(
        "ACT 1: Clean, fully-cited LLM output",
        "Every claim cites a RETRIEVED record -> ALL_CITED",
        "CYP2C19 poor metabolizers cannot activate clopidogrel [CPIC, PMID:34032273].",
    )

    # ACT 2 — fabricated citation. The token cites a source+id that was
    # never retrieved -> C2 fabricated -> GenerativeBoundary fires ->
    # caught -> fallback to deterministic narrative.
    _run_act(
        "ACT 2: Fabricated citation",
        "Cites a source never provided -> C2 refusal -> deterministic fallback",
        "This patient must switch drugs based on a study we invented [FakeDB, XREF:00000000].",
    )

    # ACT 3 — uncited claim. Confident assertion with no citation token
    # at all -> C1 missing -> fallback to deterministic narrative.
    _run_act(
        "ACT 3: Uncited confident claim",
        "Confident assertion with no citation -> C1 refusal -> deterministic fallback",
        "Clopidogrel is completely safe for absolutely every patient population everywhere.",
    )

    print("\n" + "=" * 70)
    print("✅ LLM-grounded demo complete.")
    print("   In every act, the deterministic recommendation is authoritative.")
    print("   The LLM narrative only survives when it passes citation validation;")
    print("   otherwise a named C-rule fires and the run falls back safely.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
