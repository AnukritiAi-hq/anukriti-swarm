"""Structured JSON telemetry and execution replay support.

Emits structured telemetry events that can be:
- Exported as JSONL for analysis
- Replayed for debugging
- Streamed to external systems
- Used for OpenTelemetry span creation (future)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from workflows.pipeline import PipelineTrace


@dataclass
class TelemetrySpan:
    """A single telemetry span (OpenTelemetry-compatible structure)."""

    trace_id: str
    span_id: str
    parent_span_id: str | None
    operation: str
    service: str
    start_time: str
    duration_ms: float
    status: str
    attributes: dict[str, Any] = field(default_factory=dict)


class TelemetryExporter:
    """Exports pipeline traces as structured JSON telemetry."""

    def export_spans(self, trace: PipelineTrace, state: dict[str, Any]) -> list[TelemetrySpan]:
        """Convert a pipeline trace into telemetry spans."""
        spans: list[TelemetrySpan] = []
        root_span_id = f"span_{trace.correlation_id[:8]}_root"

        # Root span
        spans.append(TelemetrySpan(
            trace_id=trace.correlation_id,
            span_id=root_span_id,
            parent_span_id=None,
            operation="pipeline.execute",
            service="anukriti-swarm",
            start_time=trace.started_at.isoformat() if trace.started_at else "",
            duration_ms=trace.total_duration_ms,
            status="ok" if all(s.status == "success" for s in trace.stages) else "error",
            attributes={
                "gene": state.get("gene", ""),
                "drug": state.get("drug", ""),
                "population": state.get("population", ""),
                "verdict": state.get("verification", {}).get("verdict", ""),
            },
        ))

        # Child spans per stage
        for i, stage in enumerate(trace.stages):
            spans.append(TelemetrySpan(
                trace_id=trace.correlation_id,
                span_id=f"span_{trace.correlation_id[:8]}_{i}",
                parent_span_id=root_span_id,
                operation=f"stage.{stage.stage}",
                service=f"agent.{stage.stage}",
                start_time="",  # Relative timing
                duration_ms=stage.duration_ms,
                status="ok" if stage.status == "success" else stage.status,
                attributes=stage.details,
            ))

        return spans

    def to_jsonl(self, spans: list[TelemetrySpan]) -> str:
        """Export spans as JSONL (one JSON object per line)."""
        lines = []
        for span in spans:
            lines.append(json.dumps({
                "trace_id": span.trace_id,
                "span_id": span.span_id,
                "parent_span_id": span.parent_span_id,
                "operation": span.operation,
                "service": span.service,
                "start_time": span.start_time,
                "duration_ms": round(span.duration_ms, 2),
                "status": span.status,
                "attributes": span.attributes,
            }, default=str))
        return "\n".join(lines)

    def to_replay_format(self, trace: PipelineTrace, state: dict[str, Any]) -> str:
        """Export as replay-friendly JSON (can re-execute pipeline)."""
        return json.dumps({
            "replay_version": "1.0",
            "correlation_id": trace.correlation_id,
            "input": {
                "gene": state.get("gene"),
                "drug": state.get("drug"),
                "population": state.get("population"),
                "allele1": state.get("allele1"),
                "allele2": state.get("allele2"),
            },
            "expected_output": {
                "phenotype": state.get("pharmacogene_result", {}).get("phenotype"),
                "risk": state.get("pharmacogene_result", {}).get("risk"),
                "verdict": state.get("verification", {}).get("verdict"),
                "confidence": state.get("verification", {}).get("confidence"),
            },
            "trace": {
                "total_ms": round(trace.total_duration_ms, 2),
                "stages": [{"name": s.stage, "ms": round(s.duration_ms, 2), "status": s.status} for s in trace.stages],
            },
        }, indent=2, default=str)
