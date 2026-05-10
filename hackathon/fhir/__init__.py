"""FHIR R4 adapters — input (FHIR resources → swarm tuple) + output (report → FHIR).

Public surface:
    PatientGenomicContext        frozen dataclass returned by input adapters
    build_context_from_fhir()    Patient + Observation/MolecularSequence → context
    build_context_from_args()    explicit args (no FHIR server) → context
    to_detected_issue()          UnifiedExecutionReport → FHIR DetectedIssue
    to_clinical_impression()     UnifiedExecutionReport → FHIR ClinicalImpression
    to_provenance()              UnifiedExecutionReport + SharpContext → FHIR Provenance
    build_response_bundle()      one call → typed dict with all three resources

Everything in this package is deterministic and synchronous. FHIR server
I/O (reads, writes) is handled by the callers (MCP tools), not here.
"""

from hackathon.fhir.input import (
    PatientGenomicContext,
    UnsupportedFHIRInput,
    build_context_from_args,
    build_context_from_fhir,
    infer_population_from_patient,
)
from hackathon.fhir.output import (
    build_response_bundle,
    to_clinical_impression,
    to_detected_issue,
    to_provenance,
)

__all__ = [
    # input
    "PatientGenomicContext",
    "UnsupportedFHIRInput",
    "build_context_from_args",
    "build_context_from_fhir",
    "infer_population_from_patient",
    # output
    "build_response_bundle",
    "to_clinical_impression",
    "to_detected_issue",
    "to_provenance",
]
