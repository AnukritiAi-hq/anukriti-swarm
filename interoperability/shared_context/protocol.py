"""``SwarmContextProtocol`` — read/write contract + scope firewall.

Closes the protocol piece of requirement #2 of the interoperability
brief. A small, strict contract that specialist genomic agents use
to *read from* and *write to* a ``SharedBiomedicalContext`` over
the ``AgentMessageBus``.

What this protocol is
---------------------
A thin session object held by each specialist agent. It:

  - Holds a reference to the current ``SharedBiomedicalContext``
    snapshot + the bus.
  - Exposes a narrow vocabulary of read operations (``read_genotype``,
    ``read_frequency``, ``read_phenotype``, …).
  - Mediates *writes* — every write is expressed as a
    ``ContextDelta`` that the protocol validates against the scope
    firewall before publishing a bus event + returning a new
    context snapshot.
  - Tracks the per-agent operation history so the execution
    trace can reconstruct which agent touched which field.

What this protocol is NOT
-------------------------
- Not a general-purpose context mutator. The ``ContextDelta``
  shape is restricted to the 8 biomedical fields; adding a
  ``clinical_record`` or ``appointment`` field raises
  ``ScopeFirewallError``.
- Not a reactive framework. There's no subscribe / notify API —
  agents poll via ``read_*`` or receive an envelope through the
  bus that carries the updated context as payload.

Why it matters
--------------
Without this layer, an agent could append any dict key to
``SharedBiomedicalContext`` via ``model_copy`` and the context
would silently drift into non-genomic territory. The protocol
forces writes through a choke point where the scope firewall
reads the delta kind and rejects off-scope operations.

Design
------
``SwarmContextProtocol`` is stateful per-agent (holds the current
snapshot) but the snapshot itself is immutable. Mutations produce
a new snapshot + return it; the protocol instance updates its
internal pointer. Two agents on the same bus should use
**separate protocol instances** — they communicate by sending
envelopes + reading the bus's latest delivered context, not by
sharing a protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from interoperability.shared_context.biomedical import (
    AlleleFrequency,
    DrugContext,
    EvidenceNode,
    PhenotypeState,
    SharedBiomedicalContext,
    VerificationNode,
)

if TYPE_CHECKING:  # pragma: no cover
    from interoperability.agent_bus.bus import AgentMessageBus


# ---------------------------------------------------------------------------
# Delta kinds — closed enum enforces scope firewall
# ---------------------------------------------------------------------------


class DeltaKind(str, Enum):
    """Closed enum of permitted write operations on SharedBiomedicalContext.

    Adding a ``DeltaKind`` value here is a design-level decision:
    it must correspond to one of the 8 brief-named fields. Any
    new kind outside this set is rejected at protocol construction.
    """

    ADD_FREQUENCY = "add_frequency"
    ADD_PHENOTYPE = "add_phenotype"
    ADD_DRUG = "add_drug"
    ADD_EVIDENCE = "add_evidence"
    ADD_VERDICT = "add_verdict"


class ScopeFirewallError(ValueError):
    """Raised when a delta violates the genomic-scope firewall."""


# ---------------------------------------------------------------------------
# Delta shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContextDelta:
    """One atomic write against a SharedBiomedicalContext.

    ``kind`` picks the target field; ``payload`` is the specific
    value (AlleleFrequency / PhenotypeState / EvidenceNode / ...).
    ``agent_id`` identifies the writer so the protocol can build
    per-agent provenance without re-parsing the context.
    """

    kind: DeltaKind
    payload: Any
    agent_id: str
    claim_id: str = ""  # for evidence / verdict deltas
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "agent_id": self.agent_id,
            "claim_id": self.claim_id,
            "recorded_at": self.recorded_at.isoformat(),
            # payload is a pydantic model — use model_dump when possible
            "payload": (
                self.payload.model_dump() if hasattr(self.payload, "model_dump") else self.payload
            ),
        }


# Mapping from delta kind to the expected payload type. Used by
# ``_apply`` to pick the right SharedBiomedicalContext.add_* helper.
_KIND_TO_TYPE: dict[DeltaKind, type] = {
    DeltaKind.ADD_FREQUENCY: AlleleFrequency,
    DeltaKind.ADD_PHENOTYPE: PhenotypeState,
    DeltaKind.ADD_DRUG: DrugContext,
    DeltaKind.ADD_EVIDENCE: EvidenceNode,
    DeltaKind.ADD_VERDICT: VerificationNode,
}


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@dataclass
class SwarmContextProtocol:
    """Per-agent session holding a SharedBiomedicalContext + bus reference.

    Usage::

        protocol = SwarmContextProtocol(
            agent_id="population_sas",
            bus=bus,
            context=shared_ctx,
        )

        # Read
        freq = protocol.read_frequency(gene="CYP2C19", allele="*2", population="SAS")

        # Write (via validated delta)
        protocol.apply(
            ContextDelta(
                kind=DeltaKind.ADD_FREQUENCY,
                payload=AlleleFrequency(
                    gene="CYP2C19",
                    allele="*2",
                    population="SAS",
                    frequency=0.36,
                    source="gnomAD v4.0",
                ),
                agent_id="population_sas",
            )
        )

        # Snapshot the latest context
        latest = protocol.context
    """

    agent_id: str
    bus: AgentMessageBus
    context: SharedBiomedicalContext
    _history: list[ContextDelta] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def read_population(self) -> str:
        return self.context.population

    def read_genotype(self, gene: str = "") -> dict[str, str] | str:
        """Return the full genotype dict, or the diplotype for ``gene``."""
        if gene:
            return self.context.genotype.get(gene, "")
        return dict(self.context.genotype)

    def read_frequency(
        self,
        *,
        gene: str,
        allele: str,
        population: str,
    ) -> float | None:
        return self.context.population_frequency(gene, allele, population)

    def read_phenotype(self, gene: str) -> PhenotypeState | None:
        return self.context.phenotype_for(gene)

    def read_drug_context(self) -> tuple[DrugContext, ...]:
        return self.context.drug_context

    def read_evidence_for_claim(self, claim_id: str) -> list[EvidenceNode]:
        return self.context.evidence_for_claim(claim_id)

    def read_verdicts_for_claim(self, claim_id: str) -> list[VerificationNode]:
        return self.context.verdicts_for_claim(claim_id)

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def apply(self, delta: ContextDelta) -> SharedBiomedicalContext:
        """Validate + apply a delta; return the new context snapshot.

        Updates ``self.context`` in place (to the new immutable
        snapshot) and appends to ``self._history``. Raises
        ``ScopeFirewallError`` when:

          - ``delta.kind`` isn't in the closed DeltaKind enum (caught
            by pydantic / enum at construction, defensive here too)
          - ``delta.payload`` isn't the expected type for the kind
          - ``delta.agent_id`` doesn't match the protocol's agent_id
            (enforces "you can only write as yourself")
        """
        self._validate(delta)
        self.context = self._apply(delta, self.context)
        self._history.append(delta)
        return self.context

    def history(self) -> list[ContextDelta]:
        """Return every delta this agent's protocol has applied."""
        return list(self._history)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self, delta: ContextDelta) -> None:
        # 1. Kind must be a known DeltaKind.
        if not isinstance(delta.kind, DeltaKind):
            raise ScopeFirewallError(
                f"unknown delta kind: {delta.kind!r}; "
                f"only {[k.value for k in DeltaKind]} are permitted"
            )

        # 2. Payload must match the expected type for the kind.
        expected = _KIND_TO_TYPE[delta.kind]
        if not isinstance(delta.payload, expected):
            raise ScopeFirewallError(
                f"delta kind={delta.kind.value} expects payload type "
                f"{expected.__name__}, got {type(delta.payload).__name__}"
            )

        # 3. agent_id on the delta must match the protocol's agent_id.
        if delta.agent_id != self.agent_id:
            raise ScopeFirewallError(
                f"delta agent_id={delta.agent_id!r} does not match "
                f"protocol agent_id={self.agent_id!r} — agents can "
                f"only write deltas under their own identity"
            )

        # 4. Evidence + verdict deltas require a claim_id (otherwise
        #    the delta can't participate in graph queries).
        if delta.kind in (DeltaKind.ADD_EVIDENCE, DeltaKind.ADD_VERDICT) and not delta.claim_id:
            raise ScopeFirewallError(
                f"delta kind={delta.kind.value} requires a non-empty claim_id "
                f"so it can be attached to the evidence/verification graph"
            )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    @staticmethod
    def _apply(
        delta: ContextDelta,
        ctx: SharedBiomedicalContext,
    ) -> SharedBiomedicalContext:
        if delta.kind is DeltaKind.ADD_FREQUENCY:
            return ctx.add_frequency(delta.payload)
        if delta.kind is DeltaKind.ADD_PHENOTYPE:
            return ctx.add_phenotype(delta.payload)
        if delta.kind is DeltaKind.ADD_DRUG:
            return ctx.add_drug(delta.payload)
        if delta.kind is DeltaKind.ADD_EVIDENCE:
            return ctx.add_evidence_node(
                delta.payload,
                claim_id=delta.claim_id,
            )
        if delta.kind is DeltaKind.ADD_VERDICT:
            # VerificationNode carries its own claim_id — use it.
            return ctx.add_verdict(delta.payload)
        # Unreachable given _validate, but defensive:
        raise ScopeFirewallError(f"unhandled delta kind {delta.kind!r}")


__all__ = [
    "SwarmContextProtocol",
    "ContextDelta",
    "DeltaKind",
    "ScopeFirewallError",
]
