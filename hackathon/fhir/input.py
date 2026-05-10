"""FHIR R4 input adapter — FHIR resources → swarm execution context.

The MCP tools accept PGx queries in three ways, in priority order:

    1. Explicit arguments (gene, drug, population, genotype)
       Used for demos and for callers that already know everything.
       Bypasses FHIR.

    2. FHIR Patient + Observation(s) with PGx genotype LOINC codes
       Used when the caller has Observations in the FHIR chart.

    3. FHIR Patient + MolecularSequence
       Used when the caller has raw sequencing data in the chart.
       Not fully implemented in v1 (diplotype extraction from a
       MolecularSequence requires calling out to anukriti-pgx-core's
       VCF adapter; we accept the resource but flag it for caller
       resolution).

This module handles cases 1 and 2 end-to-end. It exposes a single
``PatientGenomicContext`` dataclass so the MCP tools have one input
shape regardless of source.

Design choices
--------------

**Race → super-population mapping.** The US Core IG defines a race
extension with OMB-compliant values (2106-3 White, 2054-5 Black,
2028-9 Asian, etc.). We map those to the 1000-Genomes 3-letter super-
population codes our ``SuperPopulation`` enum accepts. When ancestry
is ambiguous (e.g. "2131-1 Other Race") we default to ``AMR`` (admixed
American) — the population agent for AMR is designed as the fallback
bucket precisely because of this.

**LOINC pharmacogenomic panel.** We look for Observations with one
of a short whitelist of LOINC codes commonly used for diplotype
reporting:

    53040-2  Genetic disease analysis overall interpretation
    84413-4  Gene studied (for identifying which gene)
    81252-9  Discrete genetic variant
    79716-3  Allele-name
    51968-6  Genetic variant diagnostic test

If the caller stores diplotypes in a custom Observation code they
can still call the tool with explicit ``genotype=`` and the FHIR read
becomes optional.

**No synthetic inference.** If the adapter can't find a population,
it does NOT guess. It returns a structured error that the MCP tool
surfaces as a missing-prerequisite, which in turn lets Prompt Opinion
prompt the user for the missing context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.models.population import SuperPopulation

# -----------------------------------------------------------------------------
# Errors
# -----------------------------------------------------------------------------


class UnsupportedFHIRInput(ValueError):
    """Raised when the FHIR input cannot be mapped to a PGx context.

    Callers should catch this at the MCP tool boundary and return a
    structured error to the Prompt Opinion platform that names the
    missing field, so the platform can request it from the user.
    """


# -----------------------------------------------------------------------------
# Race → SuperPopulation mapping (US Core + OMB codes)
# -----------------------------------------------------------------------------


# https://terminology.hl7.org/CodeSystem-v3-Race.html (OMB codes)
# Mapped to 1000 Genomes super-populations. Ambiguous cases default
# to AMR (admixed American) rather than being synthesized.
_OMB_RACE_TO_SUPERPOP: dict[str, SuperPopulation] = {
    "1002-5": SuperPopulation.AMR,  # American Indian or Alaska Native
    "2028-9": SuperPopulation.EAS,  # Asian (broad) — further refined below
    "2054-5": SuperPopulation.AFR,  # Black or African American
    "2076-8": SuperPopulation.AMR,  # Native Hawaiian or Other Pacific Islander
    "2106-3": SuperPopulation.EUR,  # White
    "2131-1": SuperPopulation.AMR,  # Other Race (fallback bucket)
}

# South Asian OMB detail codes (children of 2028-9 Asian).
# When one of these is present, we upgrade EAS → SAS. This is the
# entire reason Anukriti exists — CYP2C19*2 is 36% in SAS vs 15% in
# EAS. Getting this mapping right matters.
_SOUTH_ASIAN_DETAIL_CODES = {
    "2032-3",  # Asian Indian
    "2033-1",  # Bangladeshi
    "2039-6",  # Nepalese
    "2040-4",  # Pakistani
    "2041-2",  # Sri Lankan
    "2029-7",  # Bhutanese
}

# Extension URLs — we support both the US Core pattern (race inside
# an extension with nested url="ombCategory" / "detailed") and a
# simpler flat extension that just carries an OMB code.
_US_CORE_RACE_URL = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race"
_US_CORE_ETHNICITY_URL = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity"
)


# -----------------------------------------------------------------------------
# LOINC codes for PGx Observations
# -----------------------------------------------------------------------------


# Short whitelist — if the Observation.code contains any of these we
# treat the resource as a pharmacogenomic finding. Order is priority
# order for parsing.
_LOINC_PGX_CODES = {
    "53040-2",  # Genetic disease analysis overall interpretation
    "84413-4",  # Gene studied
    "81252-9",  # Discrete genetic variant
    "79716-3",  # Allele-name
    "51968-6",  # Genetic variant diagnostic test
    "84414-2",  # Genotype display name
}
_LOINC_SYSTEM = "http://loinc.org"


# -----------------------------------------------------------------------------
# PatientGenomicContext — the swarm-bound input
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class PatientGenomicContext:
    """Patient + genomic inputs ready to feed into SwarmRuntime.

    This mirrors the four fields SwarmRuntime's ``UnifiedExecutionContext.new``
    requires (``drug``, ``gene``, ``population``, ``genotype``) plus
    the patient id used for provenance.
    """

    drug: str
    gene: str
    population: SuperPopulation
    genotype: str
    patient_id: str | None = None

    # Source tracking — which FHIR resource(s) produced this context.
    # Helps with the FHIR Provenance.entity chain we emit on output.
    source_refs: tuple[str, ...] = ()

    # Free-form question that carries through to narrative synthesis.
    question: str = ""

    # Extra audit fields — kept optional so tests / demos can build
    # these without going through FHIR.
    extra: dict[str, Any] = field(default_factory=dict)

    def to_swarm_kwargs(self) -> dict[str, Any]:
        """Kwargs for ``UnifiedExecutionContext.new``."""
        return {
            "drug": self.drug,
            "gene": self.gene,
            "population": self.population,
            "genotype": self.genotype,
            "question": self.question,
        }


# -----------------------------------------------------------------------------
# Builders — explicit args + FHIR
# -----------------------------------------------------------------------------


def build_context_from_args(
    *,
    drug: str,
    gene: str,
    population: str | SuperPopulation,
    genotype: str,
    patient_id: str | None = None,
    question: str = "",
) -> PatientGenomicContext:
    """Build a context from explicit arguments. FHIR is not consulted.

    Used by the population-level tools (where no patient is in scope)
    and by the demo script.
    """

    if not drug or not drug.strip():
        raise UnsupportedFHIRInput("drug is required")
    if not gene or not gene.strip():
        raise UnsupportedFHIRInput("gene is required")
    if not genotype or not genotype.strip():
        raise UnsupportedFHIRInput("genotype is required")

    pop = _coerce_population(population)

    return PatientGenomicContext(
        drug=str(drug).strip().lower(),
        gene=str(gene).strip().upper(),
        population=pop,
        genotype=str(genotype).strip(),
        patient_id=patient_id,
        question=str(question).strip(),
    )


def build_context_from_fhir(
    *,
    drug: str,
    gene: str,
    patient: dict[str, Any] | None,
    observations: list[dict[str, Any]] | None = None,
    molecular_sequence: dict[str, Any] | None = None,
    population_override: str | SuperPopulation | None = None,
    genotype_override: str | None = None,
    question: str = "",
) -> PatientGenomicContext:
    """Build a context by inspecting FHIR resources + explicit drug/gene.

    ``drug`` and ``gene`` are always explicit — the Prompt Opinion
    A2A agent decides which drug-gene pair to query; FHIR provides
    the patient's genotype + ancestry context.

    ``population_override`` and ``genotype_override`` let callers
    bypass the FHIR inference when they already know the value. This
    is the same graceful-degradation pattern as the root
    ``demos/showcase.py``.
    """

    if not drug or not drug.strip():
        raise UnsupportedFHIRInput("drug is required")
    if not gene or not gene.strip():
        raise UnsupportedFHIRInput("gene is required")

    gene_normalized = gene.strip().upper()

    # Population — try override, then Patient.extension, then error.
    if population_override is not None:
        population = _coerce_population(population_override)
    elif patient is not None:
        population = infer_population_from_patient(patient)
    else:
        raise UnsupportedFHIRInput(
            "population could not be determined: no override and no Patient"
        )

    # Genotype — try override, then Observations (gene-filtered), then
    # a MolecularSequence stub, then error.
    source_refs: list[str] = []
    if genotype_override is not None and genotype_override.strip():
        genotype = genotype_override.strip()
    else:
        genotype = _extract_genotype_from_observations(
            observations or [],
            gene=gene_normalized,
            source_refs_out=source_refs,
        )
        if not genotype and molecular_sequence is not None:
            # v1: we don't do sequence → diplotype in-process. Surface
            # a structured abstention so the caller can route to the
            # separate variant-calling step first.
            raise UnsupportedFHIRInput(
                "MolecularSequence detected but diplotype calling is not "
                "in scope for this tool. Call the upstream variant caller "
                "(anukriti-pgx-core VCF adapter) first and retry with the "
                "resulting genotype."
            )
        if not genotype:
            raise UnsupportedFHIRInput(
                f"no PGx Observation found for gene {gene_normalized}; "
                "supply `genotype_override` or add an Observation with a "
                "LOINC PGx code (53040-2, 84413-4, 81252-9, 79716-3, 51968-6)"
            )

    patient_id = _read_id(patient) if patient else None
    if patient_id:
        source_refs.insert(0, f"Patient/{patient_id}")

    return PatientGenomicContext(
        drug=str(drug).strip().lower(),
        gene=gene_normalized,
        population=population,
        genotype=genotype,
        patient_id=patient_id,
        source_refs=tuple(source_refs),
        question=str(question).strip(),
    )


# -----------------------------------------------------------------------------
# Population inference — public because tools may want to preview it
# -----------------------------------------------------------------------------


def infer_population_from_patient(patient: dict[str, Any]) -> SuperPopulation:
    """Extract a ``SuperPopulation`` from a FHIR Patient resource.

    Looks at ``Patient.extension`` for the US Core race extension
    (``http://hl7.org/fhir/us/core/StructureDefinition/us-core-race``).
    Prefers the ``detailed`` sub-extension (which may carry an SAS
    child code) over ``ombCategory``.

    Raises ``UnsupportedFHIRInput`` if no race extension is present
    or the code is unmapped.
    """

    extensions = patient.get("extension") or []
    race_ext = next(
        (e for e in extensions if e.get("url") == _US_CORE_RACE_URL),
        None,
    )
    if race_ext is None:
        raise UnsupportedFHIRInput(
            f"Patient has no {_US_CORE_RACE_URL} extension; "
            "cannot infer super-population"
        )

    nested = race_ext.get("extension") or []

    # First pass — look for a SAS detail code.
    for sub in nested:
        if sub.get("url") != "detailed":
            continue
        code = (sub.get("valueCoding") or {}).get("code")
        if code in _SOUTH_ASIAN_DETAIL_CODES:
            return SuperPopulation.SAS

    # Second pass — use OMB category.
    for sub in nested:
        if sub.get("url") != "ombCategory":
            continue
        code = (sub.get("valueCoding") or {}).get("code")
        mapped = _OMB_RACE_TO_SUPERPOP.get(code) if code else None
        if mapped is not None:
            return mapped

    raise UnsupportedFHIRInput(
        "Patient race extension present but no usable OMB code found; "
        "expected one of: " + ", ".join(sorted(_OMB_RACE_TO_SUPERPOP.keys()))
    )


# -----------------------------------------------------------------------------
# Genotype inference
# -----------------------------------------------------------------------------


def _extract_genotype_from_observations(
    observations: list[dict[str, Any]],
    *,
    gene: str,
    source_refs_out: list[str],
) -> str | None:
    """Pick the first Observation carrying a diplotype-like value for ``gene``.

    This is a simple heuristic parser — production deployments will
    have a stricter canonical-value parser. For the hackathon we:

    1. Filter to Observations with a LOINC code in our whitelist.
    2. Check if the Observation's code.display, valueString, or
       valueCodeableConcept.text mentions our ``gene`` name.
    3. Look for a diplotype pattern (``*1/*2``, ``*2/*2``, etc.)
       or an HLA pattern (``HLA-B*15:02``).
    """

    for obs in observations:
        if not _is_pgx_observation(obs):
            continue

        # Record the source ref for Provenance even if we don't end up
        # using this Observation's value — the decision itself is audit-
        # relevant.
        obs_id = _read_id(obs)
        if obs_id:
            source_refs_out.append(f"Observation/{obs_id}")

        text_blob = _concat_observation_strings(obs)
        if gene.lower() not in text_blob.lower() and gene.replace("-", "").lower() \
                not in text_blob.lower():
            continue

        diplotype = _scan_for_diplotype(text_blob)
        if diplotype:
            return diplotype

    return None


def _is_pgx_observation(obs: dict[str, Any]) -> bool:
    """Observation has at least one coding in our LOINC PGx whitelist."""
    coding = (obs.get("code") or {}).get("coding") or []
    for c in coding:
        if c.get("system") == _LOINC_SYSTEM and c.get("code") in _LOINC_PGX_CODES:
            return True
    return False


def _concat_observation_strings(obs: dict[str, Any]) -> str:
    """Join every string-ish field we care about into one blob."""
    parts: list[str] = []

    code = obs.get("code") or {}
    if isinstance(code, dict):
        if code.get("text"):
            parts.append(str(code["text"]))
        for c in code.get("coding") or []:
            if c.get("display"):
                parts.append(str(c["display"]))

    value_cc = obs.get("valueCodeableConcept") or {}
    if isinstance(value_cc, dict):
        if value_cc.get("text"):
            parts.append(str(value_cc["text"]))
        for c in value_cc.get("coding") or []:
            if c.get("display"):
                parts.append(str(c["display"]))

    if obs.get("valueString"):
        parts.append(str(obs["valueString"]))

    for comp in obs.get("component") or []:
        if isinstance(comp, dict):
            parts.append(_concat_observation_strings(comp))

    return " | ".join(parts)


def _scan_for_diplotype(text: str) -> str | None:
    """Scan for a diplotype-like pattern in ``text``.

    Recognised shapes:
      *1/*2, *2/*2, *1/*17  (CYP2C19, CYP2D6, etc.)
      *4/*5                  (any star allele pair)
      *15:02 positive        (HLA-B with colon notation)
      15:02/positive
    """

    import re

    # CYP-style star-allele diplotype
    m = re.search(r"(\*[\w:]+)\s*/\s*(\*[\w:]+)", text)
    if m:
        return f"{m.group(1)}/{m.group(2)}"

    # HLA-B positive — common reporting style for HLA-B*15:02
    m = re.search(r"\*\s*(\d{2}:\d{2})\s*[/\s]\s*(positive|\+|carrier)", text, re.I)
    if m:
        return f"*{m.group(1)}/positive"

    return None


# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------


def _read_id(resource: dict[str, Any]) -> str | None:
    rid = resource.get("id")
    return str(rid) if rid else None


def _coerce_population(value: str | SuperPopulation) -> SuperPopulation:
    if isinstance(value, SuperPopulation):
        return value
    try:
        return SuperPopulation(str(value).strip().upper())
    except ValueError as exc:
        raise UnsupportedFHIRInput(
            f"population code {value!r} is not a canonical 1000 Genomes "
            f"super-population (AFR / AMR / EAS / EUR / SAS)"
        ) from exc
