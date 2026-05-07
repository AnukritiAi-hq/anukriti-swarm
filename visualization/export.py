"""JSON trace export for frontend integration.

Exports execution traces as structured JSON for:
- Frontend dashboard rendering
- External monitoring systems
- Audit trail persistence
- Replay and debugging
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from workflows.pipeline import PipelineTrace


def export_trace_json(trace: PipelineTrace, state: dict[str, Any]) -> str:
    """Export a complete execution trace as JSON."""
    export = {
        "version": "1.0",
        "correlation_id": trace.correlation_id,
        "timestamp": trace.started_at.isoformat() if trace.started_at else None,
        "total_duration_ms": round(trace.total_duration_ms, 1),
        "stages": [
            {
                "name": s.stage,
                "duration_ms": round(s.duration_ms, 1),
                "status": s.status,
                "details": s.details,
            }
            for s in trace.stages
        ],
        "result": {
            "gene": state.get("gene"),
            "drug": state.get("drug"),
            "population": state.get("population"),
            "diplotype": state.get("diplotype"),
            "phenotype": state.get("pharmacogene_result", {}).get("phenotype"),
            "risk": state.get("pharmacogene_result", {}).get("risk"),
            "confidence": state.get("verification", {}).get("confidence"),
            "verdict": state.get("verification", {}).get("verdict"),
            "escalation": state.get("verification", {}).get("escalation_tier"),
        },
        "evidence": {
            "citations": state.get("citations", []),
            "grounding_score": state.get("grounding_score"),
            "retrieval_count": state.get("retrieval_count"),
        },
        "population_context": state.get("population_result"),
        "recommendations": state.get("recommendations"),
    }
    return json.dumps(export, indent=2, default=str)


def export_trace_summary(trace: PipelineTrace) -> dict[str, Any]:
    """Export a lightweight trace summary (for dashboards)."""
    return {
        "correlation_id": trace.correlation_id,
        "total_ms": round(trace.total_duration_ms, 1),
        "stage_count": len(trace.stages),
        "all_passed": all(s.status == "success" for s in trace.stages),
        "stages": [{"name": s.stage, "ms": round(s.duration_ms, 1), "ok": s.status == "success"} for s in trace.stages],
    }
