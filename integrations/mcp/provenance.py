"""``MCPProvenanceStore`` — structured provenance chains for biomedical claims.

Every user-facing claim the swarm emits must be traceable back to:

    claim  →  evidence (PMID / CPIC id)
           →  deterministic rule (CPIC activity score, HW estimate, ...)
           →  verification result (verdict + confidence)
           →  generating agent (pharmacogene_cyp2c19, population_sas, ...)

This is the missing link between "we have evidence" and "we can defend
every sentence in the narrative". The shape follows W3C PROV-DM loosely:

    PROV concept        | field on ProvenanceRecord
    --------------------+---------------------------------------------
    Entity              | claim + evidence_sources
    Activity            | rule_id  + verification_verdict
    Agent               | generating_agent
    wasGeneratedBy      | generating_agent + rule_id
    wasDerivedFrom      | evidence_sources
    wasAttributedTo     | generating_agent
    wasInformedBy       | parent_claim_id  (for derived claims)

Kept as a plain JSON-safe record rather than rdflib/PROV-O so it:
  - stays cheap to persist (one Mongo insert per claim)
  - round-trips through the standard StorageBackend
  - stays readable in the in-memory backend for demos

Tools registered on the shared registry:

    provenance.record        append a single claim record
    provenance.for_claim     fetch one record by claim_id
    provenance.chain         walk the claim→parent_claim chain upward
    provenance.for_run       every claim from one correlation_id
    provenance.recent        N most recent records
    provenance.by_source     every claim that cited a given source

Design notes
------------
- Every record carries its own ``claim_id`` (uuid hex) — that is the
  stable key downstream systems (narrative generator, audit report)
  reference. ``correlation_id`` links many records to one run.
- ``rule_id`` is free-form: pharmacogene agents pass
  ``"cpic.activity_score"``, population agents
  ``"hardy_weinberg"``, verification checks
  ``"verification.checks.evidence_present"``, etc. The string is
  namespaced so querying by rule family (``rule_id.startswith(...)``) is
  cheap.
- No generative claims land here unless they pass the
  ``GenerativeBoundary`` guard — but this store doesn't enforce that;
  the orchestrator does. Anything persisted here is assumed to be
  post-verification.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from integrations.mcp.client import MCPClient
from integrations.mcp.models import MCPOrigin, MCPToolResult


PROVENANCE_COLLECTION = "provenance"


# ---------------------------------------------------------------------------
# Record shape
# ---------------------------------------------------------------------------


@dataclass
class ProvenanceRecord:
    """One entry in a provenance chain.

    Use ``to_dict()`` before handing to the backend; the store does
    that for callers automatically, so most callers can treat this as
    an internal shape.
    """

    claim: str
    generating_agent: str
    rule_id: str
    correlation_id: str
    evidence_sources: list[str] = field(default_factory=list)
    verification_verdict: str = "pending"
    confidence: float = 1.0
    parent_claim_id: str = ""  # derived claims point back to their predecessor
    origin: str = "deterministic"  # deterministic | generative | system
    metadata: dict[str, Any] = field(default_factory=dict)
    claim_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim": self.claim,
            "generating_agent": self.generating_agent,
            "rule_id": self.rule_id,
            "correlation_id": self.correlation_id,
            "evidence_sources": list(self.evidence_sources),
            "verification_verdict": self.verification_verdict,
            "confidence": float(self.confidence),
            "parent_claim_id": self.parent_claim_id,
            "origin": self.origin,
            "metadata": dict(self.metadata),
            "recorded_at": self.recorded_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


@dataclass
class MCPProvenanceStore:
    """Persistent store for structured provenance chains.

    Attaches its tools to the shared registry on construction:

        prov = MCPProvenanceStore(client)
        prov.record(ProvenanceRecord(...))
    """

    client: MCPClient
    collection: str = PROVENANCE_COLLECTION

    def __post_init__(self) -> None:
        self._register()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _register(self) -> None:
        r = self.client.registry
        r.register(
            "provenance.record",
            self._tool_record,
            description=(
                "Persist one claim record "
                "(claim→evidence→rule→verification→agent)."
            ),
            origin=MCPOrigin.AGENT,
            override=True,
        )
        r.register(
            "provenance.for_claim",
            self._tool_for_claim,
            description="Fetch a single provenance record by claim_id.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "provenance.chain",
            self._tool_chain,
            description=(
                "Walk the parent_claim_id chain upward starting at a "
                "claim_id; returns [leaf, parent, grandparent, ...]."
            ),
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "provenance.for_run",
            self._tool_for_run,
            description="All provenance records for a correlation_id.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "provenance.recent",
            self._tool_recent,
            description="N most recent provenance records across all runs.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "provenance.by_source",
            self._tool_by_source,
            description="All provenance records citing a given evidence source.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )

    # ------------------------------------------------------------------
    # Python API
    # ------------------------------------------------------------------

    def record(self, record: ProvenanceRecord | dict[str, Any]) -> MCPToolResult:
        """Persist one claim record."""
        payload = (
            record.to_dict() if isinstance(record, ProvenanceRecord) else dict(record)
        )
        return self.client.invoke(
            "provenance.record",
            args={"record": payload},
            correlation_id=str(payload.get("correlation_id", "")),
            called_by="MCPProvenanceStore",
            origin=MCPOrigin.AGENT,
        )

    def record_claim(
        self,
        *,
        claim: str,
        generating_agent: str,
        rule_id: str,
        correlation_id: str,
        evidence_sources: list[str] | None = None,
        verification_verdict: str = "pending",
        confidence: float = 1.0,
        parent_claim_id: str = "",
        origin: str = "deterministic",
        metadata: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        """Ergonomic shortcut when callers don't want to build a dataclass."""
        rec = ProvenanceRecord(
            claim=claim,
            generating_agent=generating_agent,
            rule_id=rule_id,
            correlation_id=correlation_id,
            evidence_sources=list(evidence_sources or []),
            verification_verdict=verification_verdict,
            confidence=confidence,
            parent_claim_id=parent_claim_id,
            origin=origin,
            metadata=metadata or {},
        )
        return self.record(rec)

    def for_claim(self, claim_id: str) -> MCPToolResult:
        return self.client.invoke(
            "provenance.for_claim",
            args={"claim_id": claim_id},
            called_by="MCPProvenanceStore",
        )

    def chain(self, claim_id: str, *, max_depth: int = 32) -> MCPToolResult:
        return self.client.invoke(
            "provenance.chain",
            args={"claim_id": claim_id, "max_depth": max_depth},
            called_by="MCPProvenanceStore",
        )

    def for_run(self, correlation_id: str) -> MCPToolResult:
        return self.client.invoke(
            "provenance.for_run",
            args={"correlation_id": correlation_id},
            correlation_id=correlation_id,
            called_by="MCPProvenanceStore",
        )

    def recent(self, limit: int = 20) -> MCPToolResult:
        return self.client.invoke(
            "provenance.recent",
            args={"limit": limit},
            called_by="MCPProvenanceStore",
        )

    def by_source(self, source_id: str, *, limit: int = 50) -> MCPToolResult:
        return self.client.invoke(
            "provenance.by_source",
            args={"source_id": source_id, "limit": limit},
            called_by="MCPProvenanceStore",
        )

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _tool_record(self, record: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(record, dict):
            raise TypeError("provenance.record expects a dict payload")
        claim_id = record.get("claim_id") or uuid.uuid4().hex[:16]
        if not record.get("claim"):
            raise ValueError("provenance.record requires a non-empty 'claim'")
        if not record.get("generating_agent"):
            raise ValueError("provenance.record requires 'generating_agent'")
        if not record.get("rule_id"):
            raise ValueError("provenance.record requires 'rule_id'")
        if not record.get("correlation_id"):
            raise ValueError("provenance.record requires 'correlation_id'")

        doc = dict(record)
        doc["claim_id"] = claim_id
        doc.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
        doc.setdefault("evidence_sources", [])
        doc.setdefault("confidence", 1.0)
        doc.setdefault("verification_verdict", "pending")
        doc.setdefault("origin", "deterministic")
        doc.setdefault("metadata", {})
        doc.setdefault("parent_claim_id", "")

        _id = self.client.backend.insert(self.collection, doc)
        return {"recorded": True, "_id": _id, "claim_id": claim_id}

    def _tool_for_claim(self, claim_id: str) -> dict[str, Any] | None:
        if not claim_id:
            raise ValueError("provenance.for_claim requires claim_id")
        rows = self.client.backend.query(
            self.collection, {"claim_id": claim_id}, limit=1
        )
        return rows[0] if rows else None

    def _tool_chain(
        self, claim_id: str, max_depth: int = 32
    ) -> list[dict[str, Any]]:
        """Walk parent links upward, newest claim first.

        ``max_depth`` is a cycle-safety bound; well-formed chains are
        typically 2–4 deep.
        """
        if not claim_id:
            raise ValueError("provenance.chain requires claim_id")
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        current = claim_id
        while current and current not in seen and len(out) < int(max_depth):
            seen.add(current)
            doc = self._tool_for_claim(current)
            if not doc:
                break
            out.append(doc)
            current = doc.get("parent_claim_id") or ""
        return out

    def _tool_for_run(self, correlation_id: str) -> list[dict[str, Any]]:
        if not correlation_id:
            raise ValueError("provenance.for_run requires correlation_id")
        return self.client.backend.query(
            self.collection,
            {"correlation_id": correlation_id},
            sort=[("recorded_at", 1)],  # chronological within a run
        )

    def _tool_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.client.backend.query(
            self.collection, None, sort=[("recorded_at", -1)], limit=int(limit)
        )

    def _tool_by_source(
        self, source_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Every claim whose ``evidence_sources`` contains ``source_id``.

        The in-memory backend's minimal filter language doesn't support
        array-contains, so we post-filter here. The MongoDB backend
        could shortcut with ``{"evidence_sources": source_id}``; doing
        both paths is worth ~20 lines of conditional logic, so we keep
        the post-filter path uniformly for code clarity.
        """
        if not source_id:
            raise ValueError("provenance.by_source requires source_id")
        rows = self.client.backend.query(
            self.collection, None, sort=[("recorded_at", -1)]
        )
        hits = [r for r in rows if source_id in (r.get("evidence_sources") or [])]
        return hits[: int(limit)]


__all__ = [
    "MCPProvenanceStore",
    "ProvenanceRecord",
    "PROVENANCE_COLLECTION",
]
