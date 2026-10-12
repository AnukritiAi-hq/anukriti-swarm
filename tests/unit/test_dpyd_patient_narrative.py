"""The patient-facing dose text must come from the engine, never be re-derived.

`_patient_narrative` used to classify the DPYD genotype itself, against two
hardcoded literal sets:

    no_func_set  = {"*2A", "*13"}
    dec_func_set = {"c.2846A>T", "HapB3"}

The engine's pinned DPYD table carries twelve actionable alleles. Those sets
named four, so the other eight — ``*8``, ``*10``, ``*12``, ``c.1129-5923C>G``,
``c.1236G>A``, ``c.1475C>T``, ``c.2279C>T``, ``c.2639G>T`` — matched neither
branch and fell through to the Normal Metabolizer fallback, which tells the
**patient** to take a standard fluoropyrimidine dose.

Two of the eight are the ones that hurt most here:

* ``c.2279C>T`` is 0.63% in GenomeIndia (n=9,768) and 0.000% in Europeans. It
  is the allele the South Asian coverage argument rests on, so the product
  found the carrier the European panels miss and then told them to take a full
  dose.
* ``c.1236G>A`` is how the engine labels a tag-only HapB3 call from 0.9.0
  onward. That is the modal Indian HapB3 presentation, so the literal
  ``"HapB3"`` in ``dec_func_set`` stopped matching the common case the moment
  that labelling landed — a silent drop introduced by an upstream rename that
  nothing here could detect.

The missing alleles were the symptom. The defect was re-deriving a clinical
conclusion the deterministic layer had already reached: a second
implementation can only agree with the first by coincidence, and when it
disagrees nothing notices. `core/verification/safety.py` re-derives from the
same two allele strings, so it agrees with itself and passes.

These tests pin the property rather than the allele list — that the narrative
and the engine cannot disagree — so adding an allele to the engine's table
cannot silently reintroduce the gap.
"""

from __future__ import annotations

import pytest

from core.models.population import SuperPopulation
from core.runtime.context import UnifiedExecutionContext
from core.runtime.runtime import _patient_narrative, _phenotype_for


def _ctx(genotype: str, drug: str = "fluorouracil") -> UnifiedExecutionContext:
    return UnifiedExecutionContext(
        gene="DPYD",
        drug=drug,
        genotype=genotype,
        population=SuperPopulation.SAS,
    )


# Every actionable allele in the engine's pinned DPYD table, with the eight
# that previously fell through marked. Carried explicitly so the regression is
# readable, but the property tests below are what actually hold the line.
PREVIOUSLY_MISSED = [
    "*8",
    "*10",
    "*12",
    "c.1129-5923C>G",
    "c.1236G>A",
    "c.1475C>T",
    "c.2279C>T",
    "c.2639G>T",
]

STANDARD_DOSE_PHRASE = "per standard dosing"


@pytest.mark.parametrize("allele", PREVIOUSLY_MISSED)
def test_an_actionable_allele_is_never_told_to_take_a_standard_dose(allele) -> None:
    """The eight that fell through. Each one is a carrier sent to full dose."""
    text = _patient_narrative(_ctx(f"*1/{allele}"), [])
    assert STANDARD_DOSE_PHRASE not in text, (
        f"*1/{allele} produced the Normal Metabolizer fallback, which tells "
        f"the patient to take a standard fluoropyrimidine dose. This allele is "
        f"actionable in the engine's own table."
    )
    assert "Intermediate Metabolizer" in text
    assert "50%" in text


def test_c2279ct_the_south_asian_allele_reduces_the_dose() -> None:
    """Called out on its own because it is the product's whole thesis.

    0.63% in 9,768 Indian genomes, 0.000% in Europeans, on no commercial panel
    the 2024 AMP consensus surveyed. Detecting it and then recommending a full
    dose is worse than not detecting it, because it carries the authority of a
    positive finding.
    """
    text = _patient_narrative(_ctx("*1/c.2279C>T"), [])
    assert "Intermediate Metabolizer" in text
    assert "reduce starting" in text.lower()
    assert STANDARD_DOSE_PHRASE not in text


@pytest.mark.parametrize(
    "genotype",
    [
        "*1/*1",
        "*1/*9A",
        "*1/c.2279C>T",
        "*1/HapB3",
        "*1/c.1236G>A",
        "*1/*2A",
        "*2A/*2A",
        "*1/c.2846A>T",
        "*1/*12",
    ],
)
def test_the_narrative_never_disagrees_with_the_engine(genotype) -> None:
    """The property, not the list.

    Whatever phenotype the deterministic layer assigns is the phenotype the
    patient text must describe. If these two can diverge at all, the specific
    alleles that happen to diverge today are an accident of which literals
    someone remembered to type.
    """
    phenotype = str(_phenotype_for(_ctx(genotype)).get("phenotype") or "").strip()
    text = _patient_narrative(_ctx(genotype), [])

    if phenotype == "Normal Metabolizer":
        assert "Normal Metabolizer" in text
    elif phenotype == "Intermediate Metabolizer":
        assert "Intermediate Metabolizer" in text
        assert STANDARD_DOSE_PHRASE not in text
    elif phenotype == "Poor Metabolizer":
        assert "Poor Metabolizer" in text
        assert "AVOID" in text
        assert STANDARD_DOSE_PHRASE not in text
    else:
        assert "did not resolve to a CPIC phenotype" in text
        assert STANDARD_DOSE_PHRASE not in text


def test_an_unresolved_phenotype_is_a_refusal_not_an_all_clear() -> None:
    """There was no branch for this at all, so it reached the Normal fallback.

    A refusal rendered as an all-clear is the worst available failure mode: the
    one case where the system knows it does not know, reported as the one case
    where there is nothing to worry about.
    """
    text = _patient_narrative(_ctx("*1/not-a-real-allele"), [])
    assert STANDARD_DOSE_PHRASE not in text
    assert "not an all-clear" in text
    assert "did not resolve to a CPIC phenotype" in text


def test_a_poor_metabolizer_still_gets_the_contraindication() -> None:
    """The change must not weaken the branch that already worked."""
    text = _patient_narrative(_ctx("*2A/*2A"), [])
    assert "Poor Metabolizer" in text
    assert "AVOID" in text
