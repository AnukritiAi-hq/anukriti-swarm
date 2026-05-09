"""``ProvenancePropagationLayer`` — stamps MCP provenance on envelopes.

Closes the provenance piece of requirement #2 of the
interoperability brief.

What this layer does
--------------------
Sits between the ``AgentMessageBus`` and the ``MCPProvenanceStore``.
Every time an ``AgentContextEnvelope`` carries evidence references,
the propagation layer:

  1. **Records** the claim → evidence link into MCP's provenance
     store, so the audit trail persists across runs.
  2. **Resolves** the stored provenance chain back onto the envelope
     (stamps ``evidence_references`` with any upstream ancestors)
     so downstream agents see the full causal history, not just
     the sources this hop cited.
  3. **Tags** the envelope with MCP ``claim_id`` when the store
     generated one, letting later agents query provenance by id.

What this layer does NOT do
---------------------------
- Does **not** generate provenance for non-biomedical contexts.
  Scope firewall enforced via the envelope's
  ``biomedical_context_type`` (closed enum).
- Does **not** bypass the MCP ``observability`` seam — every
  ``provenance.record`` tool call flows through the MCP registry
  + audit backend, inheriting the observability the MCP layer
  already provides.

Design
------
Stateless (one callable per client). Can be attached to an
``AgentMessageBus`` as a ``BusObserver`` so provenance stamping
happens automatically on every ``delivered`` event, or called
imperatively via ``stamp(envelope)`` when an agent wants tighter
control.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from integrations.mcp.client import MCPClient
from integrations.mcp.provenance import MCPProvenanceStore, ProvenanceRecord
from interoperability.shared_context.envelope import (
    AgentContextEnvelope,
    BiomedicalContextType,
)

if TYPE_CHECKING:  # pragma: no cover
    from interoperability.agent_bus.bus import AgentMessageBus


# Map from BiomedicalContextType → MCP rule_id prefix. Keeps provenance
# records namespaced by biomedical concern so queries can filter.
_CONTEXT_TYPE_RULE_PREFIX: dict[BiomedicalContextType, str] = {
    BiomedicalContextType.POPULATION: "population.hardy_weinberg",
    BiomedicalContextType.GENOTYPE: "cpic.diplotype",
    BiomedicalContextType.PHARMACOGENE: "cpic.activity_score",
    BiomedicalContextType.EVIDENCE: "evidence.retrieval",
    BiomedicalContextType.VERIFICATION: "verification.summary",
    BiomedicalContextType.CONFIDENCE: "confidence.propagation",
    BiomedicalContextType.PROVENANCE: "provenance.chain",
}


@dataclass
class ProvenancePropagationLayer:
    """Propagates MCP provenance onto envelopes transiting the bus.

    Two usage patterns:

        layer = ProvenancePropagationLayer(client=MCPClient())

        # (a) Imperative — agent stamps before replying:
        new_env = layer.stamp(envelope)

        # (b) Observational — attach to the bus to stamp on delivery:
        bus.observe(layer.as_observer())
    """

    client: MCPClient
    # When True, also resolve upstream provenance chains and merge the
    # extra source_ids onto the envelope's evidence_references.
    resolve_upstream: bool = True

    def __post_init__(self) -> None:
        self.store = MCPProvenanceStore(client=self.client)

    # ------------------------------------------------------------------
    # Imperative API
    # ------------------------------------------------------------------

    def stamp(
        self, envelope: AgentContextEnvelope,
    ) -> AgentContextEnvelope:
        """Persist provenance for this envelope + return an annotated copy.

        The returned envelope carries:
          - ``evidence_references`` extended with any upstream source_ids
            the MCP chain knew about (when ``resolve_upstream=True``)
          - ``payload['_provenance_claim_id']`` pointing to the MCP
            provenance record this envelope generated

        Safe-to-call when the envelope has no evidence: we still record
        a provenance node (so the audit trail shows "agent X produced a
        verdict with no cited evidence") but skip the upstream resolve.
        """
        # Build the ProvenanceRecord.
        rule_id = _CONTEXT_TYPE_RULE_PREFIX.get(
            envelope.biomedical_context_type, "unknown"
        )
        # Use the message_id as claim_id so downstream lookups can
        # join envelopes to their provenance records without a second
        # index. Fall back to a random hex only if message_id is empty
        # (shouldn't happen — pydantic defaults it).
        claim_id = envelope.message_id or None
        # Derive a human-readable claim text from the envelope kind +
        # payload summary. Keeps provenance records self-describing
        # without forcing agents to craft claim strings.
        claim_text = self._summarise_claim(envelope)

        record = ProvenanceRecord(
            claim=claim_text,
            generating_agent=envelope.originating_agent,
            rule_id=rule_id,
            correlation_id=envelope.workflow_id,
            evidence_sources=list(envelope.evidence_references),
            verification_verdict=envelope.verification_state.value,
            confidence=envelope.confidence_value,
            claim_id=claim_id or "",   # ProvenanceRecord auto-generates if blank
        )
        result = self.store.record(record)
        stored_claim_id = (
            str(result.data.get("claim_id", ""))
            if result.success and isinstance(result.data, dict)
            else claim_id or ""
        )

        new_payload = dict(envelope.payload or {})
        if stored_claim_id:
            new_payload["_provenance_claim_id"] = stored_claim_id

        # Upstream resolve — if the envelope cites a source, look up
        # any provenance records that already cite it and merge their
        # other sources onto our envelope. This is the "causal ancestry
        # is preserved across agent hops" guarantee.
        upstream_sources: list[str] = []
        if self.resolve_upstream and envelope.evidence_references:
            upstream_sources = self._gather_upstream_sources(
                envelope.evidence_references,
                exclude_claim_id=stored_claim_id,
            )

        # Annotated copy.
        annotated = envelope.model_copy(update={"payload": new_payload})
        if upstream_sources:
            annotated = annotated.with_evidence(*upstream_sources)
        return annotated

    # ------------------------------------------------------------------
    # Bus-observer adapter
    # ------------------------------------------------------------------

    def as_observer(self):
        """Return a BusObserver callable that stamps on 'delivered' events.

        Attach via ``bus.observe(layer.as_observer())``.
        """
        def _observer(envelope: AgentContextEnvelope, event: str) -> None:
            if event != "delivered":
                return
            try:
                self.stamp(envelope)
            except Exception:
                # Never let a provenance-stamp failure disrupt message
                # delivery. The bus has already delivered the envelope;
                # we just missed recording the chain.
                pass
        return _observer

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _summarise_claim(envelope: AgentContextEnvelope) -> str:
        """Build a human-readable claim string for the provenance record."""
        kind = envelope.biomedical_context_type.value
        agent = envelope.originating_agent
        workflow = envelope.workflow_id
        # One-line summary — don't dump the full payload.
        payload_summary = ""
        if envelope.payload:
            # Include a couple of headline fields if they exist.
            for key in ("gene", "drug", "phenotype", "population", "frequency"):
                if key in envelope.payload:
                    payload_summary += f" {key}={envelope.payload[key]!r}"
        return (
            f"[{kind}] agent={agent} workflow={workflow}"
            + (payload_summary if payload_summary else "")
        )

    def _gather_upstream_sources(
        self,
        source_ids: tuple[str, ...],
        *,
        exclude_claim_id: str = "",
    ) -> list[str]:
        """For each source_id, collect other source_ids on provenance records
        that also cited it. Skips our just-stored claim to avoid a
        self-referencing loop."""
        seen: set[str] = set(source_ids)
        out: list[str] = []
        for sid in source_ids:
            try:
                res = self.store.by_source(sid)
            except Exception:
                continue
            if not res.success or not res.data:
                continue
            for rec in res.data:
                if not isinstance(rec, dict):
                    continue
                if rec.get("claim_id") == exclude_claim_id:
                    continue
                for other in rec.get("evidence_sources") or []:
                    if isinstance(other, str) and other and other not in seen:
                        seen.add(other)
                        out.append(other)
        return out


__all__ = ["ProvenancePropagationLayer"]
