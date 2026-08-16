"""Regression tests for the SAS/DPYD population-aware uncertainty flag.

Locks in the outcome of the 2026-07-28 audit
(``anukriti_docs/DPYD_SAS_OVERRIDE_AUDIT_2026-07-28.md``), which replaced a
hard synthesis block with a named uncertainty flag.

The behaviour these tests pin down, and why each matters:

* The flag **must not** withhold the deterministic answer. The original
  implementation set ``allows_synthesis = False`` on the strength of a
  toxicity claim that three primary papers disagree about
  (Hariprakash 2018 / Naushad 2021 / Atasilp 2025) and a frequency claim
  that real gnomAD v2.1.1 data refutes outright. Blocking on contested
  evidence is the same error class as asserting a EUR-derived call
  everywhere.
* The rule id **must not** be ``U4``. That id already means "KG path bundle
  supplied but empty" in ``UncertaintyScoringEngine``
  (``core/evidence_sufficiency/uncertainty/engine.py``); reusing it made two
  unrelated conditions indistinguishable in an audit trail.
* The flag is emitted as ``UNCERTAINTY_TRANSITION``, not
  ``SAFE_ABSTENTION`` — nothing is being abstained from.

Before this file existed, the override had **zero** test coverage in any
repo, which is how the unsupported refusal survived from 2026-06-06 to
2026-07-28 unchallenged.
"""

from __future__ import annotations

import pytest
from core.models.population import SuperPopulation
from core.runtime.context import UnifiedExecutionContext
from core.runtime.events import InMemoryEventStream, RuntimeEventKind
from core.runtime.runtime import SwarmRuntime

RULE = "P1_SAS_DPYD_CONTESTED"


@pytest.fixture
def runtime() -> SwarmRuntime:
    return SwarmRuntime(event_stream=InMemoryEventStream())


def _ctx(population: SuperPopulation, genotype: str, gene: str = "DPYD"):
    return UnifiedExecutionContext.new(
        drug="fluorouracil",
        gene=gene,
        population=population,
        genotype=genotype,
    )


def _flags(report_ctx) -> list[dict]:
    checkpoint = (report_ctx.evidence_state or {}).get("checkpoint") or {}
    return checkpoint.get("population_uncertainty_flags", [])


def _events(runtime: SwarmRuntime, kind: RuntimeEventKind) -> list:
    return [e for e in runtime.event_stream.events if e.kind is kind]


class TestContestedAlleleFlag:
    """A SAS patient carrying *9A or M166V gets a named flag, not a refusal."""

    @pytest.mark.parametrize("genotype", ["*1/*9A", "*1/M166V", "*9A/*9A", "*9A/M166V"])
    def test_flag_attached_for_sas_contested_alleles(self, runtime, genotype):
        ctx = _ctx(SuperPopulation.SAS, genotype)
        runtime.run(ctx)

        flags = _flags(ctx)
        assert len(flags) == 1, f"expected exactly one flag for {genotype}"
        assert flags[0]["rule"] == RULE
        assert flags[0]["gene"] == "DPYD"
        assert flags[0]["population"] == "SAS"

    def test_flag_does_not_block_synthesis(self, runtime):
        """The core correction: the hook leaves the sufficiency verdict alone.

        Asserted against the hook in isolation rather than by comparing two
        genotypes, because different DPYD genotypes legitimately get
        different sufficiency verdicts from Stage 4 (``*1/*9A`` is in fact
        blocked by rule R3 — "recommendation evidence missing" — on its own
        merits). That R3 block is exactly what the withdrawn override used to
        overwrite: its own comment said it replaced an already-blocked
        "generic reason (R3 etc)" because "our refusal is more informative",
        substituting an unsupported claim for an honest, correctly-named one.
        """
        ctx = _ctx(SuperPopulation.SAS, "*1/*9A")
        ctx.evidence_state = {"checkpoint": {"allows_synthesis": True, "blocking_reason": ""}}

        runtime._apply_population_aware_overrides(ctx)

        checkpoint = ctx.evidence_state["checkpoint"]
        assert (
            checkpoint["allows_synthesis"] is True
        ), "the flag must not withhold the deterministic answer"
        assert checkpoint["blocking_reason"] == ""
        assert len(checkpoint["population_uncertainty_flags"]) == 1

    def test_flag_preserves_a_pre_existing_deterministic_refusal(self, runtime):
        """When Stage 4 legitimately blocks, its named reason must survive."""
        ctx = _ctx(SuperPopulation.SAS, "*1/*9A")
        ctx.evidence_state = {
            "checkpoint": {
                "allows_synthesis": False,
                "blocking_reason": "sufficiency:block:R3: recommendation evidence missing",
            }
        }

        runtime._apply_population_aware_overrides(ctx)

        checkpoint = ctx.evidence_state["checkpoint"]
        assert checkpoint["allows_synthesis"] is False
        assert (
            "R3" in checkpoint["blocking_reason"]
        ), "the honest R3 refusal must not be overwritten by this flag"
        assert RULE not in checkpoint["blocking_reason"]

    def test_emits_uncertainty_transition_not_safe_abstention(self, runtime):
        ctx = _ctx(SuperPopulation.SAS, "*1/*9A")
        runtime.run(ctx)

        transitions = [
            e
            for e in _events(runtime, RuntimeEventKind.UNCERTAINTY_TRANSITION)
            if e.payload.get("rule") == RULE
        ]
        assert len(transitions) == 1
        assert transitions[0].payload["allows_synthesis_changed"] is False

        abstentions = [
            e
            for e in _events(runtime, RuntimeEventKind.SAFE_ABSTENTION)
            if e.payload.get("rule") == RULE
        ]
        assert abstentions == [], "a contested-evidence flag is not an abstention"

    def test_rule_id_does_not_collide_with_uncertainty_engine_u4(self, runtime):
        """U4 is already 'KG path bundle supplied but empty'. Don't reuse it."""
        ctx = _ctx(SuperPopulation.SAS, "*1/*9A")
        runtime.run(ctx)

        assert _flags(ctx)[0]["rule"] != "U4"
        assert not _flags(ctx)[0]["rule"].startswith("U4")

    def test_reason_cites_the_contested_evidence_honestly(self, runtime):
        """The refusal text used to assert a toxicity risk the papers dispute."""
        ctx = _ctx(SuperPopulation.SAS, "*1/M166V")
        runtime.run(ctx)
        reason = _flags(ctx)[0]["reason"]

        # names all three primary sources rather than one
        for source in ("Hariprakash 2018", "Naushad 2021", "Atasilp 2025"):
            assert source in reason
        # states the real, non-enriched frequency direction
        assert "0.0906" in reason and "0.1004" in reason
        # does not repeat the withdrawn "27% carrier frequency" claim
        assert "27%" not in reason


class TestScopeIsNarrow:
    """The flag fires only for SAS + DPYD + a contested allele."""

    def test_no_flag_for_non_sas_population(self, runtime):
        ctx = _ctx(SuperPopulation.EUR, "*1/*9A")
        runtime.run(ctx)
        assert _flags(ctx) == []

    def test_no_flag_for_cpic_actionable_alleles(self, runtime):
        """*2A is a real CPIC no-function allele — it needs no research flag."""
        ctx = _ctx(SuperPopulation.SAS, "*1/*2A")
        runtime.run(ctx)
        assert _flags(ctx) == []

    def test_no_flag_for_other_genes(self, runtime):
        ctx = _ctx(SuperPopulation.SAS, "*2/*2", gene="CYP2C19")
        runtime.run(ctx)
        assert _flags(ctx) == []


class TestFrequencyRecordsMatchRealGnomad:
    """The records behind the flag must be real, and correctly directional."""

    def test_neither_allele_is_sas_enriched(self):
        from datasets.pharmfreq.allele_frequencies import DPYD_FREQUENCIES

        by_key = {(r.allele, r.population): r for r in DPYD_FREQUENCIES}
        for allele in ("*9A", "M166V"):
            sas = by_key[(allele, "SAS")].frequency
            eur = by_key[(allele, "EUR")].frequency
            assert sas / eur < 1.2, (
                f"{allele} SAS/EUR = {sas / eur:.2f}; neither allele is "
                "South-Asian-enriched in real gnomAD v2.1.1 data, and no "
                "refusal may be justified on enrichment grounds"
            )

    def test_afr_is_the_population_maximum_for_9a(self):
        """The withdrawn record claimed AFR 0.050; real value is 0.4131."""
        from datasets.pharmfreq.allele_frequencies import DPYD_FREQUENCIES

        nine_a = {r.population: r.frequency for r in DPYD_FREQUENCIES if r.allele == "*9A"}
        assert max(nine_a, key=nine_a.get) == "AFR"

    def test_provenance_is_a_real_queried_source(self):
        from datasets.pharmfreq.allele_frequencies import DPYD_FREQUENCIES

        for r in DPYD_FREQUENCIES:
            if r.allele in ("*9A", "M166V"):
                assert r.source == "gnomAD"
                # the withdrawn records cited a mis-dated paper as "literature"
                assert "Hariprakash" not in r.version
                assert r.function == "normal_function", (
                    "CPIC assigns Normal function to both (live API, "
                    "2026-07-28); the records must not imply otherwise"
                )
