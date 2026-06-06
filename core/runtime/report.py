"""``UnifiedExecutionReport`` — frozen final record for one unified run.

Phase 1, commit 2 of the Unified Orchestration + Visualization brief.

Snapshotted from a ``UnifiedExecutionContext`` once the
``SwarmRuntime`` lifecycle completes. Carries every brief-named field
(requirement #5):

    orchestration_trace      from the orchestrator stage
    activated_agents         every specialist that fired
    evidence_sufficiency     the full CheckpointResult (coverage +
                             conflict + sufficiency decision +
                             verdict + uncertainty + bias + trace +
                             allows_synthesis)
    uncertainty_analysis     a flattened view of the uncertainty
                             tier + recommended action + bias
                             findings for dashboards
    graph_traversal          KG path bundle (population-weighted)
                             produced by MultiHopReasoner
    deterministic_rules      rule ids triggered across the run
                             (CPIC activity score, HLA risk allele,
                             sufficiency R1..R12, verdict V1..V10,
                             uncertainty U1..U9, stopping signals,
                             etc.)
    provenance_chain         MCP ProvenanceRecord summaries
    final_recommendation     the recommendation text + strength +
                             evidence refs, OR the refusal reason
                             if allows_synthesis is False

Frozen; ``to_dict()`` is JSON-safe and crosses the FastAPI boundary
unchanged in phase 3.

The report is the **single return value** of ``SwarmRuntime.run()``.
Consumers (demos, FastAPI endpoints, tests) never reach into the
context directly — they read the report.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.runtime.context import UnifiedExecutionContext


@dataclass(frozen=True)
class UnifiedExecutionReport:
    """Frozen final record of a single unified swarm run.

    Fields
    ------
    Identity:
      report_id             16-char hex id
      correlation_id        linkage to MCP + context
      generated_at          ISO timestamp

    Scope keys (mirrored from the context, never mutated):
      drug / gene / population / genotype / question

    Lifecycle output (brief req #5 — every bullet is a field):
      orchestration_trace   dict from orchestrator stage
      activated_agents      tuple of agent names in activation order
      evidence_sufficiency  dict (from CheckpointResult.to_dict); None
                            when the sufficiency stage hasn't run
      uncertainty_analysis  flattened dict: score / action / tier /
                            bias_findings; None if uncertainty stage
                            skipped
      graph_traversal       list of GraphPath.to_dict; empty when no
                            KG bundle was produced
      deterministic_rules   tuple of rule ids triggered across the run
                            (dedup preserves first-occurrence order)
      provenance_chain      list of ProvenanceRecord dicts
      final_recommendation  dict: text / strength / evidence_refs /
                            allows_synthesis / blocking_reason

    Summary:
      total_duration_ms     wall time for the full run
      errors                tuple of non-fatal error strings from
                            the context
    """

    drug: str
    gene: str
    population: str
    genotype: str
    question: str

    correlation_id: str
    activated_agents: tuple[str, ...]
    orchestration_trace: dict[str, Any] | None
    evidence_sufficiency: dict[str, Any] | None
    uncertainty_analysis: dict[str, Any] | None
    graph_traversal: tuple[dict[str, Any], ...]
    deterministic_rules: tuple[str, ...]
    provenance_chain: tuple[dict[str, Any], ...]
    final_recommendation: dict[str, Any]

    total_duration_ms: float = 0.0
    errors: tuple[str, ...] = ()
    grounded_narrative: dict[str, Any] | None = None

    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_context(
        cls,
        ctx: UnifiedExecutionContext,
        *,
        total_duration_ms: float = 0.0,
    ) -> UnifiedExecutionReport:
        """Snapshot a context into a frozen report.

        Extracts:
          - evidence_sufficiency from ctx.evidence_state['checkpoint']
            when present
          - uncertainty_analysis from the checkpoint's uncertainty +
            bias fields when present (flattened for dashboard use)
          - graph_traversal from ctx.graph_state['paths'] when present
          - deterministic_rules from every stage's rule ids
          - provenance_chain from ctx.provenance_state['records']
          - final_recommendation from the checkpoint's gate + the
            ctx's narrative_output

        Every extraction is defensive — missing stages yield empty
        tuples / None rather than raising, so a partial run (e.g. a
        safe-abstention path that stops after sufficiency) still
        produces a valid report.
        """

        checkpoint = cls._maybe(ctx.evidence_state, "checkpoint")
        uncertainty_flat = cls._flatten_uncertainty(checkpoint)
        graph_paths = cls._extract_graph_paths(ctx.graph_state)
        provenance = cls._extract_provenance(ctx.provenance_state)
        rules = cls._collect_rule_ids(ctx, checkpoint)
        recommendation = cls._build_recommendation(ctx, checkpoint)

        return cls(
            drug=ctx.drug,
            gene=ctx.gene,
            population=ctx.population.value,
            genotype=ctx.genotype,
            question=ctx.question,
            correlation_id=ctx.correlation_id,
            activated_agents=tuple(ctx.activated_agents),
            orchestration_trace=ctx.orchestration_trace,
            evidence_sufficiency=checkpoint,
            uncertainty_analysis=uncertainty_flat,
            graph_traversal=tuple(graph_paths),
            deterministic_rules=rules,
            provenance_chain=tuple(provenance),
            final_recommendation=recommendation,
            total_duration_ms=round(float(total_duration_ms), 3),
            errors=tuple(ctx.errors),
            grounded_narrative=(ctx.narrative_output or {}).get("grounded"),
        )

    # ------------------------------------------------------------------
    # Extraction internals — defensive, silent on missing stages
    # ------------------------------------------------------------------

    @staticmethod
    def _maybe(state: dict[str, Any] | None, key: str) -> dict[str, Any] | None:
        """Return state[key] if state is a dict and key exists, else None."""

        if isinstance(state, dict):
            val = state.get(key)
            if isinstance(val, dict):
                return val
        return None

    @staticmethod
    def _flatten_uncertainty(
        checkpoint: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Flatten CheckpointResult uncertainty + bias for dashboards."""

        if checkpoint is None:
            return None
        return {
            "uncertainty_score": checkpoint.get("uncertainty_score"),
            "uncertainty_action": checkpoint.get("uncertainty_action"),
            "bias_findings": list(checkpoint.get("bias_findings") or []),
        }

    @staticmethod
    def _extract_graph_paths(
        graph_state: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Return the graph-path bundle as a list of dicts."""

        if not isinstance(graph_state, dict):
            return []
        paths = graph_state.get("paths") or []
        return [dict(p) for p in paths if isinstance(p, dict)]

    @staticmethod
    def _extract_provenance(
        provenance_state: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Return the provenance records as a list of dicts."""

        if not isinstance(provenance_state, dict):
            return []
        records = provenance_state.get("records") or []
        return [dict(r) for r in records if isinstance(r, dict)]

    @staticmethod
    def _collect_rule_ids(
        ctx: UnifiedExecutionContext,
        checkpoint: dict[str, Any] | None,
    ) -> tuple[str, ...]:
        """Dedup rule ids from across the lifecycle, preserving order."""

        seen: set[str] = set()
        ordered: list[str] = []

        def _add(value: str | None) -> None:
            if not value:
                return
            text = str(value).strip()
            if not text or text in seen:
                return
            seen.add(text)
            ordered.append(text)

        # Orchestration steps carry rule_ids in their payloads
        if isinstance(ctx.orchestration_trace, dict):
            for step in ctx.orchestration_trace.get("steps", []):
                if isinstance(step, dict):
                    _add(step.get("rule_id"))

        # Verification state may carry a list of rule ids directly
        if isinstance(ctx.verification_state, dict):
            for rid in ctx.verification_state.get("rule_ids", []):
                _add(rid)

        # Checkpoint surfaces the sufficiency + verdict + uncertainty
        # rule ids via its result structure
        if isinstance(checkpoint, dict):
            _add(checkpoint.get("sufficiency_decision"))
            _add(checkpoint.get("verdict_rule_id"))
            _add(checkpoint.get("uncertainty_score"))

        return tuple(ordered)

    @staticmethod
    def _build_recommendation(
        ctx: UnifiedExecutionContext,
        checkpoint: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Assemble the final recommendation view.

        When the checkpoint blocked synthesis, the recommendation is a
        refusal record naming the blocking layer + reason. Otherwise
        the recommendation comes from the context's narrative_output
        (if produced) or from the sufficiency layer's evidence_refs.
        """

        allows = bool(checkpoint and checkpoint.get("allows_synthesis", False))
        blocking_reason = str(checkpoint.get("blocking_reason", "")) if checkpoint else ""

        if not allows:
            return {
                "allows_synthesis": False,
                "blocking_reason": blocking_reason,
                "text": "",
                "strength": "refused",
                "evidence_refs": [],
            }

        narrative = ctx.narrative_output or {}
        # Prefer 'patient' audience text when present; fall back to any.
        text = narrative.get("patient") or next(iter(narrative.values()), "")
        ev_refs: list[str] = []
        if checkpoint:
            # Take evidence_refs off the checkpoint's trace when available
            trace = checkpoint.get("trace", {})
            if isinstance(trace, dict):
                ev_refs = list(trace.get("retrieved_evidence") or [])

        return {
            "allows_synthesis": True,
            "blocking_reason": "",
            "text": text,
            "strength": "recommended" if text else "deterministic",
            "evidence_refs": ev_refs,
        }

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "correlation_id": self.correlation_id,
            "drug": self.drug,
            "gene": self.gene,
            "population": self.population,
            "genotype": self.genotype,
            "question": self.question,
            "activated_agents": list(self.activated_agents),
            "orchestration_trace": self.orchestration_trace,
            "evidence_sufficiency": self.evidence_sufficiency,
            "uncertainty_analysis": self.uncertainty_analysis,
            "graph_traversal": [dict(p) for p in self.graph_traversal],
            "deterministic_rules": list(self.deterministic_rules),
            "provenance_chain": [dict(r) for r in self.provenance_chain],
            "final_recommendation": dict(self.final_recommendation),
            "total_duration_ms": self.total_duration_ms,
            "errors": list(self.errors),
            "grounded_narrative": self.grounded_narrative,
        }


__all__ = ["UnifiedExecutionReport"]
