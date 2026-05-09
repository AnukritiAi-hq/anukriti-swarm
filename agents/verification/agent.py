"""``BiomedicalVerificationAgent`` — composes the four safety engines.

This is the public surface the orchestrator + demo talk to. Runs the
four engines in the right order against a single orchestration run
and returns a unified ``VerificationOutcome``:

    1. BiomedicalClaimValidator    (shape)
    2. EvidenceGroundingEngine     (existence)
    3. SafetyConstraintEngine      (biomedical truth + block decision)
    4. ProvenanceValidator         (persisted chain completeness)

The agent doesn't mutate the run dict or the orchestration context.
It reads inputs, produces a ``VerificationOutcome`` with:

    traces:       list[VerificationTrace] from every engine
    decision:     SafetyDecision (tier + block flag)
    grounding:    GroundingReport (coverage + missing sources)
    provenance:   ProvenanceReport (chain completeness)
    is_safe:      convenience property

The ``decision.block`` flag is the single signal the orchestrator
uses to decide whether to surface an output. Nothing else in this
agent can override it.

Backward compatibility
----------------------
This **does not** replace the legacy ``VerificationAgent`` in
``agents.verification.legacy_agent`` — that one is used by the
``workflows.pharmacogenomic_pipeline`` LangGraph-style pipeline and
keeps its original contract. Callers who want the full safety
engine use ``BiomedicalVerificationAgent`` explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.verification.claim_validator import BiomedicalClaimValidator
from core.verification.grounding import EvidenceGroundingEngine, GroundingReport
from core.verification.provenance_validator import (
    ProvenanceReport,
    ProvenanceValidator,
)
from core.verification.safety import SafetyConstraintEngine, SafetyDecision
from core.verification.trace import VerificationTrace
from integrations.mcp.client import MCPClient


# ---------------------------------------------------------------------------
# Outcome shape
# ---------------------------------------------------------------------------


@dataclass
class VerificationOutcome:
    """Aggregate result of running the safety engine on one orchestration run.

    Carries every artifact the engines produced, in a stable order
    the demo and audit report consume.
    """

    correlation_id: str
    traces: list[VerificationTrace] = field(default_factory=list)
    decision: SafetyDecision | None = None
    grounding: GroundingReport | None = None
    provenance: ProvenanceReport | None = None

    @property
    def is_safe(self) -> bool:
        """True when the safety decision says this output is deliverable.

        ``decision.block`` is the single authoritative signal.
        """
        return self.decision is not None and not self.decision.block

    @property
    def tier(self) -> str:
        return self.decision.tier.value if self.decision else "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "is_safe": self.is_safe,
            "tier": self.tier,
            "decision": self.decision.to_dict() if self.decision else None,
            "grounding": self.grounding.to_dict() if self.grounding else None,
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "traces": [t.to_dict() for t in self.traces],
        }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


@dataclass
class BiomedicalVerificationAgent:
    """Composes the 4 safety engines against one orchestration run.

    Construction is cheap (stateless engines) so callers can build
    one per orchestrator or one per run — doesn't matter. Pass an
    ``MCPClient`` so the grounding + provenance engines can reach
    the shared backend.

    Parameters
    ----------
    client:
        MCPClient for grounding + provenance engines. When None,
        grounding and provenance checks are skipped (claim validator
        and safety engine still run — useful for offline tests).
    strict_cpic_alignment:
        Passed through to ``SafetyConstraintEngine``.
    allow_unknown_alleles:
        Passed through to ``SafetyConstraintEngine``.
    """

    client: MCPClient | None = None
    strict_cpic_alignment: bool = True
    allow_unknown_alleles: bool = False

    def __post_init__(self) -> None:
        self.claim_validator = BiomedicalClaimValidator()
        self.safety = SafetyConstraintEngine(
            strict_cpic_alignment=self.strict_cpic_alignment,
            allow_unknown_alleles=self.allow_unknown_alleles,
        )
        self.grounding: EvidenceGroundingEngine | None = None
        self.provenance: ProvenanceValidator | None = None
        if self.client is not None:
            self.grounding = EvidenceGroundingEngine(
                client=self.client, validator=self.claim_validator
            )
            self.provenance = ProvenanceValidator(client=self.client)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify_run(
        self,
        run: dict[str, Any],
        *,
        correlation_id: str = "",
    ) -> VerificationOutcome:
        """Run the 4-layer safety engine against one orchestration run.

        Order:
          1. Claim validator       shape of every claim
          2. Grounding engine      MCP evidence existence
                                   (skipped when client is None)
          3. Safety engine         biomedical correctness + block
                                   decision (runs regardless of client)
          4. Provenance validator  persisted chain completeness
                                   (skipped when client is None)

        Returns a ``VerificationOutcome`` with ``traces`` in the
        order the engines produced them.
        """
        outcome = VerificationOutcome(correlation_id=correlation_id)

        # --- 1 + 2: claims & grounding ---
        if self.grounding is not None:
            claim_traces, grounding_report = self.grounding.ground_run(
                run, correlation_id=correlation_id
            )
            outcome.grounding = grounding_report
        else:
            claim_traces = self.claim_validator.validate_run(
                run, correlation_id=correlation_id
            )
        outcome.traces.extend(claim_traces)

        # --- 3: safety engine (always runs) ---
        outcome.decision = self.safety.apply(
            run=run,
            prior_traces=claim_traces,
            correlation_id=correlation_id,
        )
        outcome.traces.extend(outcome.decision.traces)

        # --- 4: provenance audit (skipped when client is None) ---
        if self.provenance is not None and correlation_id:
            prov_traces, prov_report = self.provenance.validate_run(correlation_id)
            outcome.traces.extend(prov_traces)
            outcome.provenance = prov_report

        return outcome

    # ------------------------------------------------------------------
    # Convenience renderer
    # ------------------------------------------------------------------

    def audit_report(self, outcome: VerificationOutcome) -> str:
        """Render a plain-text audit report for the outcome.

        Closes requirement #8 (deterministic audit reports: why the
        recommendation was made / which rules triggered / which
        evidence was used / which agents participated). Consumed by
        the safety demo.
        """
        lines: list[str] = []
        lines.append("=" * 68)
        lines.append(f"DETERMINISTIC VERIFICATION AUDIT — {outcome.correlation_id}")
        lines.append("=" * 68)
        lines.append(f"Outcome: tier={outcome.tier}  is_safe={outcome.is_safe}")
        if outcome.decision:
            lines.append(f"Reason:  {outcome.decision.reason}")
            lines.append(
                f"Score:   conf={outcome.decision.score.confidence:.2f} "
                f"level={outcome.decision.score.confidence_level.value}"
            )
        if outcome.grounding:
            g = outcome.grounding
            lines.append(
                f"Evidence: {g.sources_resolved}/{g.sources_requested} "
                f"source(s) resolved "
                f"(coverage={g.coverage:.0%})"
            )
            if g.missing_source_ids:
                lines.append(
                    f"  missing: {', '.join(g.missing_source_ids[:5])}"
                    f"{' …' if len(g.missing_source_ids) > 5 else ''}"
                )
        if outcome.provenance:
            p = outcome.provenance
            lines.append(
                f"Provenance: {p.records_examined} record(s) "
                f"{'clean' if p.is_clean else 'with gaps'}"
            )
            if p.dangling_parents:
                lines.append(f"  dangling parents: {', '.join(p.dangling_parents[:5])}")

        lines.append("-" * 68)
        lines.append("Per-claim traces:")
        for t in outcome.traces:
            lines.append(
                f"  [{t.state:<4}] {t.validator:<28} "
                f"rule={t.rule_id:<32} "
                f"conf={t.confidence:.2f}"
            )
            if t.claim:
                lines.append(f"         claim: {t.claim[:80]}")
            if t.reason:
                lines.append(f"         reason: {t.reason[:90]}")
            if t.escalation_events:
                for ev in t.escalation_events:
                    lines.append(
                        f"         → escalation: {ev.action} — {ev.reason[:60]}"
                    )

        lines.append("=" * 68)
        return "\n".join(lines)


__all__ = ["BiomedicalVerificationAgent", "VerificationOutcome"]
