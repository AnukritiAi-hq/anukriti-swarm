"""Unit tests for ``hackathon.fhir`` (input + output adapters)."""

from __future__ import annotations

import pytest

from core.models.population import SuperPopulation
from hackathon.fhir import (
    PatientGenomicContext,
    UnsupportedFHIRInput,
    build_context_from_args,
    build_context_from_fhir,
    build_response_bundle,
    infer_population_from_patient,
    to_clinical_impression,
    to_detected_issue,
    to_provenance,
)
from hackathon.sharp import SharpContext


# =============================================================================
# Fixtures
# =============================================================================


US_CORE_RACE_URL = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race"


def _make_patient(race_codes: list[dict[str, str]] | None = None) -> dict:
    extensions = []
    if race_codes:
        nested = []
        for coding in race_codes:
            nested.append(
                {
                    "url": coding.pop("url", "ombCategory"),
                    "valueCoding": coding,
                }
            )
        extensions.append({"url": US_CORE_RACE_URL, "extension": nested})
    return {
        "resourceType": "Patient",
        "id": "patient-007",
        "extension": extensions,
        "name": [{"family": "Patel", "given": ["Priya"]}],
    }


def _make_pgx_observation(
    *,
    gene: str = "CYP2C19",
    value_text: str = "*2/*2",
    loinc: str = "53040-2",
) -> dict:
    return {
        "resourceType": "Observation",
        "id": "obs-pgx-1",
        "status": "final",
        "code": {
            "coding": [
                {"system": "http://loinc.org", "code": loinc, "display": "Genetic"}
            ],
            "text": f"{gene} genotype",
        },
        "valueString": f"{gene} {value_text}",
    }


def _run_report():
    """Actually execute the swarm once and return a real report.

    These tests exercise the round-trip from FHIR in → swarm → FHIR out,
    so we use the real report rather than a stub.
    """
    from core.runtime import SwarmRuntime, UnifiedExecutionContext

    rt = SwarmRuntime()
    ctx = UnifiedExecutionContext.new(
        drug="clopidogrel",
        gene="CYP2C19",
        population="SAS",
        genotype="*2/*2",
    )
    return rt.run(ctx)


# =============================================================================
# build_context_from_args
# =============================================================================


class TestBuildContextFromArgs:
    def test_happy_path(self) -> None:
        ctx = build_context_from_args(
            drug="Clopidogrel",
            gene="cyp2c19",
            population="SAS",
            genotype="*2/*2",
        )

        assert ctx.drug == "clopidogrel"
        assert ctx.gene == "CYP2C19"
        assert ctx.population == SuperPopulation.SAS
        assert ctx.genotype == "*2/*2"

    def test_accepts_superpopulation_enum(self) -> None:
        ctx = build_context_from_args(
            drug="clopidogrel",
            gene="CYP2C19",
            population=SuperPopulation.AFR,
            genotype="*4/*4",
        )
        assert ctx.population == SuperPopulation.AFR

    def test_rejects_empty_drug(self) -> None:
        with pytest.raises(UnsupportedFHIRInput):
            build_context_from_args(drug="", gene="G", population="SAS", genotype="*1/*1")

    def test_rejects_invalid_population(self) -> None:
        with pytest.raises(UnsupportedFHIRInput):
            build_context_from_args(
                drug="d", gene="G", population="MARS", genotype="*1/*1"
            )

    def test_to_swarm_kwargs_matches_expected_shape(self) -> None:
        ctx = build_context_from_args(
            drug="clopidogrel",
            gene="CYP2C19",
            population="SAS",
            genotype="*2/*2",
        )
        kwargs = ctx.to_swarm_kwargs()

        assert kwargs == {
            "drug": "clopidogrel",
            "gene": "CYP2C19",
            "population": SuperPopulation.SAS,
            "genotype": "*2/*2",
            "question": "",
        }


# =============================================================================
# infer_population_from_patient
# =============================================================================


class TestInferPopulation:
    def test_sas_from_asian_indian_detail(self) -> None:
        patient = _make_patient(
            race_codes=[
                {"code": "2028-9", "display": "Asian"},
                {"url": "detailed", "code": "2032-3", "display": "Asian Indian"},
            ]
        )

        assert infer_population_from_patient(patient) == SuperPopulation.SAS

    def test_eas_from_broad_asian_ombcategory(self) -> None:
        patient = _make_patient(
            race_codes=[{"code": "2028-9", "display": "Asian"}]
        )

        assert infer_population_from_patient(patient) == SuperPopulation.EAS

    def test_eur_from_white(self) -> None:
        patient = _make_patient(race_codes=[{"code": "2106-3", "display": "White"}])
        assert infer_population_from_patient(patient) == SuperPopulation.EUR

    def test_afr_from_black(self) -> None:
        patient = _make_patient(
            race_codes=[{"code": "2054-5", "display": "Black or African American"}]
        )
        assert infer_population_from_patient(patient) == SuperPopulation.AFR

    def test_amr_from_other(self) -> None:
        patient = _make_patient(race_codes=[{"code": "2131-1", "display": "Other"}])
        assert infer_population_from_patient(patient) == SuperPopulation.AMR

    def test_raises_when_no_race_extension(self) -> None:
        patient = _make_patient(race_codes=None)
        with pytest.raises(UnsupportedFHIRInput, match="extension"):
            infer_population_from_patient(patient)

    def test_raises_when_unknown_code(self) -> None:
        patient = _make_patient(race_codes=[{"code": "9999-9"}])
        with pytest.raises(UnsupportedFHIRInput, match="OMB"):
            infer_population_from_patient(patient)


# =============================================================================
# build_context_from_fhir (Observation path)
# =============================================================================


class TestBuildContextFromFHIR:
    def test_patient_plus_observation_full_path(self) -> None:
        patient = _make_patient(
            race_codes=[
                {"code": "2028-9"},
                {"url": "detailed", "code": "2032-3"},
            ]
        )
        obs = _make_pgx_observation(gene="CYP2C19", value_text="*2/*2")

        ctx = build_context_from_fhir(
            drug="clopidogrel",
            gene="CYP2C19",
            patient=patient,
            observations=[obs],
        )

        assert ctx.drug == "clopidogrel"
        assert ctx.gene == "CYP2C19"
        assert ctx.population == SuperPopulation.SAS
        assert ctx.genotype == "*2/*2"
        assert ctx.patient_id == "patient-007"
        assert "Patient/patient-007" in ctx.source_refs
        assert "Observation/obs-pgx-1" in ctx.source_refs

    def test_genotype_override_bypasses_observation_parse(self) -> None:
        patient = _make_patient(race_codes=[{"code": "2106-3"}])

        ctx = build_context_from_fhir(
            drug="warfarin",
            gene="CYP2C9",
            patient=patient,
            observations=[],
            genotype_override="*1/*3",
        )

        assert ctx.genotype == "*1/*3"
        assert ctx.population == SuperPopulation.EUR

    def test_population_override_bypasses_race_inference(self) -> None:
        obs = _make_pgx_observation(gene="CYP2C19", value_text="*2/*2")

        ctx = build_context_from_fhir(
            drug="clopidogrel",
            gene="CYP2C19",
            patient=None,
            observations=[obs],
            population_override="SAS",
        )

        assert ctx.population == SuperPopulation.SAS

    def test_raises_when_no_patient_and_no_population_override(self) -> None:
        with pytest.raises(UnsupportedFHIRInput, match="population"):
            build_context_from_fhir(
                drug="clopidogrel",
                gene="CYP2C19",
                patient=None,
                observations=[],
            )

    def test_raises_when_no_genotype_found(self) -> None:
        patient = _make_patient(race_codes=[{"code": "2028-9"}])

        with pytest.raises(UnsupportedFHIRInput, match="Observation"):
            build_context_from_fhir(
                drug="clopidogrel",
                gene="CYP2C19",
                patient=patient,
                observations=[],
            )

    def test_molecularsequence_without_call_is_structured_abstention(self) -> None:
        patient = _make_patient(race_codes=[{"code": "2028-9"}])
        mol = {"resourceType": "MolecularSequence", "id": "mol-1"}

        with pytest.raises(UnsupportedFHIRInput, match="variant caller"):
            build_context_from_fhir(
                drug="clopidogrel",
                gene="CYP2C19",
                patient=patient,
                observations=[],
                molecular_sequence=mol,
            )


# =============================================================================
# FHIR output adapters
# =============================================================================


class TestFhirOutput:
    @pytest.fixture(scope="class")
    def report(self):
        return _run_report()

    @pytest.fixture
    def sharp(self):
        return SharpContext(
            url="https://fhir.example.org/r4",
            token="Bearer demo-tok",
            patient_id="patient-007",
            session_id="po-session-42",
        )

    def test_to_detected_issue_has_required_fields(self, report) -> None:
        di = to_detected_issue(report, patient_id="patient-007")

        assert di["resourceType"] == "DetectedIssue"
        assert di["status"] == "final"
        assert di["severity"] in {"high", "moderate", "low"}
        assert di["subject"]["reference"] == "Patient/patient-007"
        assert di["detail"]
        assert len(di["evidence"]) >= 1
        assert di["implicated"][0]["display"] == "clopidogrel"

    def test_to_detected_issue_includes_mitigation_when_narrative_suggests(
        self, report
    ) -> None:
        di = to_detected_issue(report, patient_id="patient-007")

        # The swarm's narrative for CYP2C19*2/*2 + clopidogrel recommends
        # prasugrel or ticagrelor. At least one mitigation should appear.
        assert len(di.get("mitigation", [])) >= 1

    def test_to_clinical_impression_has_summary_and_findings(self, report) -> None:
        ci = to_clinical_impression(
            report, patient_id="patient-007", detected_issue_id="di-foo"
        )

        assert ci["resourceType"] == "ClinicalImpression"
        assert ci["status"] in {"completed", "in-progress"}
        assert ci["summary"]
        assert len(ci["finding"]) >= 2
        assert ci["problem"][0]["reference"] == "DetectedIssue/di-foo"

    def test_to_provenance_cross_links_targets(self, report, sharp) -> None:
        prov = to_provenance(
            report,
            sharp_context=sharp,
            target_refs=["DetectedIssue/di-1", "ClinicalImpression/ci-1"],
        )

        targets = {t["reference"] for t in prov["target"]}
        assert "DetectedIssue/di-1" in targets
        assert "ClinicalImpression/ci-1" in targets

        # Two agents: Anukriti Superpower + SHARP session
        assert len(prov["agent"]) == 2

    def test_to_provenance_has_sharp_session_agent(self, report, sharp) -> None:
        prov = to_provenance(
            report, sharp_context=sharp, target_refs=["DetectedIssue/x"]
        )

        # At least one agent should carry the SHARP session identifier.
        agent_values = [
            a["who"].get("identifier", {}).get("value")
            for a in prov["agent"]
        ]
        sharp_agent = next(
            (v for v in agent_values if v and sharp.session_id in v), None
        )
        assert sharp_agent is not None

    def test_build_response_bundle_is_cross_linked(self, report, sharp) -> None:
        bundle = build_response_bundle(
            report, sharp_context=sharp, patient_id="patient-007"
        )

        di_id = bundle["detectedIssue"]["id"]
        ci_id = bundle["clinicalImpression"]["id"]

        # ClinicalImpression.problem points at DetectedIssue
        assert bundle["clinicalImpression"]["problem"][0]["reference"] == (
            f"DetectedIssue/{di_id}"
        )

        # Provenance.target includes both
        targets = {t["reference"] for t in bundle["provenance"]["target"]}
        assert f"DetectedIssue/{di_id}" in targets
        assert f"ClinicalImpression/{ci_id}" in targets

        # Top-level summary fields are populated
        assert bundle["recommendation"]
        assert bundle["strength"]
        assert bundle["allowsSynthesis"] is True


# =============================================================================
# End-to-end: FHIR Patient + Observation → swarm → FHIR bundle
# =============================================================================


def test_end_to_end_fhir_in_fhir_out() -> None:
    """Full round-trip: real FHIR resources in, real FHIR bundle out.

    This is the test that matters most — it exercises everything the
    MCP tools will exercise at runtime, minus only the MCP transport.
    """
    from core.runtime import SwarmRuntime, UnifiedExecutionContext

    patient = _make_patient(
        race_codes=[
            {"code": "2028-9"},
            {"url": "detailed", "code": "2032-3"},
        ]
    )
    obs = _make_pgx_observation(gene="CYP2C19", value_text="*2/*2")

    pgx = build_context_from_fhir(
        drug="clopidogrel",
        gene="CYP2C19",
        patient=patient,
        observations=[obs],
    )

    rt = SwarmRuntime()
    ctx = UnifiedExecutionContext.new(**pgx.to_swarm_kwargs())
    report = rt.run(ctx)

    sharp = SharpContext(
        url="https://fhir.example.org/r4",
        token="Bearer demo-tok",
        patient_id=pgx.patient_id,
        session_id="po-session-demo",
    )
    bundle = build_response_bundle(
        report, sharp_context=sharp, patient_id=pgx.patient_id
    )

    # Assertions
    assert bundle["detectedIssue"]["subject"]["reference"] == "Patient/patient-007"
    assert bundle["recommendation"]
    assert bundle["strength"]

    # Must have cited at least one evidence ref
    evidence = bundle["detectedIssue"].get("evidence", [])
    assert len(evidence) >= 1

    # Provenance agent should include the SHARP session reference
    prov_agents = [
        a["who"].get("identifier", {}).get("value", "")
        for a in bundle["provenance"]["agent"]
    ]
    assert any("po-session-demo" in v for v in prov_agents)
