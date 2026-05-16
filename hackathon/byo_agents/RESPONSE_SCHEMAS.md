# JSON Response Schemas

Paste these into the **JSON Response Format** field for each agent in
Prompt Opinion. They enforce structured, machine-readable responses
so downstream agents can branch without parsing prose.

---

## PGx Consultant — response schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PGxConsultantResponse",
  "type": "object",
  "oneOf": [
    {
      "title": "Success",
      "required": ["fhir_resources", "abstention_rule_id"],
      "properties": {
        "fhir_resources": {
          "type": "array",
          "items": {"type": "object"},
          "description": "DetectedIssue / ClinicalImpression / Provenance resources returned by the Superpower"
        },
        "abstention_rule_id": {
          "oneOf": [
            {"type": "null"},
            {
              "type": "string",
              "pattern": "^(R[0-9]+|V[0-9]+|U[0-9]+|EUROCENTRIC_IMBALANCE|ANCESTRY_SCARCITY|UNSUPPORTED_EXTRAPOLATION)$"
            }
          ]
        },
        "rule_family": {
          "type": "string",
          "enum": ["sufficiency_decision", "set_verifier", "uncertainty", "bias", null]
        },
        "reason": {"type": "string"},
        "tool_invoked": {
          "type": "string",
          "enum": [
            "pgx_analyze_patient",
            "pgx_population_risk",
            "pgx_retrieve_evidence",
            "pgx_verify_recommendation",
            "pgx_sufficiency_check"
          ]
        }
      }
    },
    {
      "title": "MissingField",
      "required": ["error", "field", "message"],
      "properties": {
        "error": {"type": "string", "const": "missing_field"},
        "field": {"type": "string"},
        "message": {"type": "string"}
      }
    },
    {
      "title": "ToolFailure",
      "required": ["error", "tool", "detail", "retryable"],
      "properties": {
        "error": {"type": "string", "const": "tool_failure"},
        "tool": {"type": "string"},
        "detail": {"type": "string"},
        "retryable": {"type": "boolean"}
      }
    }
  ]
}
```

---

## Evidence Auditor — response schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "EvidenceAuditorVerdict",
  "type": "object",
  "required": [
    "verdict",
    "rule_id",
    "rule_family",
    "findings",
    "approved_citations",
    "blocked_citations",
    "bias_findings"
  ],
  "properties": {
    "verdict": {
      "type": "string",
      "enum": ["APPROVED", "NEEDS_REVIEW", "BLOCKED"]
    },
    "rule_id": {
      "type": "string",
      "pattern": "^(R[0-9]+|V[0-9]+|U[0-9]+|EUROCENTRIC_IMBALANCE|ANCESTRY_SCARCITY|UNSUPPORTED_EXTRAPOLATION|citation_integrity)$"
    },
    "rule_family": {
      "type": "string",
      "enum": [
        "sufficiency_decision",
        "set_verifier",
        "uncertainty",
        "bias",
        "citation_integrity"
      ]
    },
    "findings": {
      "type": "array",
      "minItems": 4,
      "maxItems": 4,
      "items": {
        "type": "object",
        "required": ["check", "outcome", "detail"],
        "properties": {
          "check": {
            "type": "string",
            "enum": ["sufficiency", "citations", "bias", "verification"]
          },
          "outcome": {
            "type": "string",
            "enum": ["pass", "warn", "fail"]
          },
          "detail": {"type": "string"},
          "rule_id": {
            "oneOf": [{"type": "null"}, {"type": "string"}]
          }
        }
      }
    },
    "approved_citations": {
      "type": "array",
      "items": {
        "type": "string",
        "pattern": "^(PMID:|CPIC:|PharmGKB:)"
      }
    },
    "blocked_citations": {
      "type": "array",
      "items": {"type": "string"}
    },
    "bias_findings": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": [
          "EUROCENTRIC_IMBALANCE",
          "ANCESTRY_SCARCITY",
          "UNSUPPORTED_EXTRAPOLATION"
        ]
      }
    },
    "caveat": {
      "oneOf": [{"type": "null"}, {"type": "string"}]
    }
  }
}
```

---

## Prescriber — response schema

Leave this **blank** in Prompt Opinion. The Prescriber is the
user-facing surface; it produces formatted markdown, not JSON. The
structured data flows between Prescriber → Consultant → Auditor in
JSON; the user sees only the rendered markdown.

If you want the Prescriber to *also* emit a structured payload
(e.g. for logging / analytics), use this optional schema:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "PrescriberMetadata",
  "type": "object",
  "required": ["response_markdown", "assessment"],
  "properties": {
    "response_markdown": {"type": "string"},
    "assessment": {
      "type": "object",
      "required": ["drug", "gene", "genotype", "population", "phenotype", "citations"],
      "properties": {
        "drug": {"type": "string"},
        "gene": {"type": "string"},
        "genotype": {"type": "string"},
        "population": {
          "type": "string",
          "enum": ["SAS", "EAS", "AFR", "EUR", "AMR"]
        },
        "phenotype": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "citations": {
          "type": "array",
          "items": {"type": "string"}
        },
        "bias_findings": {
          "type": "array",
          "items": {"type": "string"}
        },
        "abstention_rule_id": {
          "oneOf": [{"type": "null"}, {"type": "string"}]
        },
        "auditor_verdict": {
          "oneOf": [
            {"type": "null"},
            {
              "type": "string",
              "enum": ["APPROVED", "NEEDS_REVIEW", "BLOCKED"]
            }
          ]
        }
      }
    }
  }
}
```

This metadata schema is optional. Use it if your Prompt Opinion
deployment captures structured traces for later analysis.

---

## Why enums, not free strings?

Every enum above maps to a closed vocabulary defined in the main
swarm codebase:
- Rule ids (R1-R12, V1-V10, U1-U9) — `core/evidence_sufficiency/`
- Bias kinds — `PopulationEvidenceBiasDetector` in the same module
- Super-populations — `core/models/population.SuperPopulation`
- Rule families — subsystem boundaries in the sufficiency layer

A string that doesn't match an enum value indicates drift from the
scope firewall. Prompt Opinion's JSON-schema validation will reject
it at the response boundary, matching the closed-enum guarantee the
Python codebase enforces at the type boundary.
