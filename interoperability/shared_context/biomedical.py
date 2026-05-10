"""``SharedBiomedicalContext`` — bundled domain state for agent collaboration.

Closes requirement #7 of the interoperability brief. Holds exactly
the 8 brief-named fields specialist agents read and write when they
collaborate peer-to-peer through the ``AgentMessageBus``:

    ancestry            ancestry / super-population descriptor
    population          population code (SAS / AFR / EUR / EAS / AMR)
    genotype            per-gene diplotype
    allele_frequencies  observed frequencies per (gene, allele, population)
    phenotype_state     per-gene phenotype + activity score + origin
    drug_context        drug(s) under evaluation + CPIC alignment
    evidence_graph      directed graph: claim → evidence source → confidence
    verification_graph  directed graph: claim → safety check → verdict

Why a new context class, not just re-use SwarmExecutionContext?
--------------------------------------------------------------
Two reasons:

  1. **Graph shape.** The brief specifically requires an
     evidence_graph and verification_graph — directed structures
     a specialist agent can query ("which claims support this
     recommendation?"). SwarmExecutionContext carries flat lists
     of ``evidence_refs`` + ``verification_report``; it can't
     answer graph queries.

  2. **Scope firewall.** SharedBiomedicalContext is the ONLY
     context shape that flows through the genomic bus. If a
     future agent tries to attach clinical-record fields, there's
     nowhere to put them — the context doesn't grow those
     attributes. SwarmExecutionContext is more permissive because
     it's an orchestration-internal type.

Design
------
Thin wrapper: builds from a SwarmExecutionContext via
``.from_swarm_context(ctx)``, exposes the 8 brief fields as
first-class attributes, and surfaces the two graphs as lightweight
dicts keyed by node id. Pure data — no methods that reach out to
MCP or call the orchestrator.

Immutability
------------
Frozen pydantic model. Agents annotate by producing a new context
via ``.add_evidence(...)`` / ``.add_phenotype(...)`` / ``.add_verdict(...)``
helpers. Matches the envelope idiom.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Graph node shapes
# ---------------------------------------------------------------------------


class EvidenceNode(BaseModel):
    """One node in the evidence_graph.

    Represents a concrete citation (PMID, CPIC guideline id, PharmGKB
    entry, PharmVar allele record). Edges connect a claim to one or
    more EvidenceNodes via ``EvidenceEdge``.
    """

    source_id: str  # e.g. "PMID:34032273"
    source_kind: str = "unknown"  # "pmid" | "cpic" | "pharmgkb" | "pharmvar"
    title: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(frozen=True)


class EvidenceEdge(BaseModel):
    """Directed edge claim → evidence source."""

    claim_id: str
    source_id: str
    relation: str = "supports"  # "supports" | "contradicts" | "qualifies"
    weight: float = 1.0
    model_config = ConfigDict(frozen=True)


class VerificationNode(BaseModel):
    """One node in the verification_graph — a single safety check."""

    check_id: str  # e.g. "claim-abc:cpic.alignment"
    claim_id: str
    check_name: str  # e.g. "cpic.alignment"
    verdict: str  # "pass" | "warn" | "fail"
    reason: str = ""
    confidence: float = 1.0
    model_config = ConfigDict(frozen=True)


class VerificationEdge(BaseModel):
    """Directed edge claim → verification check."""

    claim_id: str
    check_id: str
    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Phenotype + drug sub-records
# ---------------------------------------------------------------------------


class PhenotypeState(BaseModel):
    """Per-gene phenotype + activity score + provenance origin."""

    gene: str
    diplotype: str  # e.g. "*2/*2"
    activity_score: float | None = None
    phenotype: str = ""  # "Poor Metabolizer" | ...
    origin: str = "deterministic"
    confidence: float = 1.0
    rule_id: str = "cpic.activity_score"
    model_config = ConfigDict(frozen=True)


class DrugContext(BaseModel):
    """Drug under evaluation + any CPIC alignment metadata."""

    drug: str
    guideline_id: str = ""  # e.g. "CPIC:CYP2C19:clopidogrel:2022"
    recommendation: str = ""
    strength: str = ""  # "strong" | "moderate" | "optional"
    model_config = ConfigDict(frozen=True)


class AlleleFrequency(BaseModel):
    """One (gene, allele, population) frequency observation."""

    gene: str
    allele: str
    population: str
    frequency: float
    sample_n: int | None = None
    source: str = ""
    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Shared context
# ---------------------------------------------------------------------------


class SharedBiomedicalContext(BaseModel):
    """Immutable bundled biomedical state for peer-to-peer agent collab.

    Constructed once per orchestration run, then threaded through
    ``AgentContextEnvelope.payload['context_ref']`` so specialist
    agents read the same snapshot without re-fetching.

    Frozen — annotations via ``.add_*`` helpers produce new instances.
    """

    workflow_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # --- 8 brief-named fields ---
    ancestry: str = ""
    population: str = ""
    genotype: dict[str, str] = Field(default_factory=dict)
    allele_frequencies: tuple[AlleleFrequency, ...] = ()
    phenotype_state: tuple[PhenotypeState, ...] = ()
    drug_context: tuple[DrugContext, ...] = ()
    evidence_graph_nodes: tuple[EvidenceNode, ...] = ()
    evidence_graph_edges: tuple[EvidenceEdge, ...] = ()
    verification_graph_nodes: tuple[VerificationNode, ...] = ()
    verification_graph_edges: tuple[VerificationEdge, ...] = ()

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    # ------------------------------------------------------------------
    # Queries (graph-flavoured)
    # ------------------------------------------------------------------

    def evidence_for_claim(self, claim_id: str) -> list[EvidenceNode]:
        """Return every evidence node connected to ``claim_id``."""
        linked_sources = {e.source_id for e in self.evidence_graph_edges if e.claim_id == claim_id}
        return [n for n in self.evidence_graph_nodes if n.source_id in linked_sources]

    def verdicts_for_claim(self, claim_id: str) -> list[VerificationNode]:
        """Return every verification node linked to ``claim_id``."""
        return [n for n in self.verification_graph_nodes if n.claim_id == claim_id]

    def population_frequency(
        self,
        gene: str,
        allele: str,
        population: str,
    ) -> float | None:
        """Lookup the recorded frequency for a (gene, allele, pop) triple."""
        for af in self.allele_frequencies:
            if af.gene == gene and af.allele == allele and af.population == population:
                return af.frequency
        return None

    def phenotype_for(self, gene: str) -> PhenotypeState | None:
        """Lookup the phenotype state for a given gene."""
        for ps in self.phenotype_state:
            if ps.gene == gene:
                return ps
        return None

    def summary(self) -> dict[str, Any]:
        """Compact one-liner summary for demos / dashboards."""
        return {
            "workflow_id": self.workflow_id,
            "ancestry": self.ancestry,
            "population": self.population,
            "gene_count": len(self.genotype),
            "frequency_count": len(self.allele_frequencies),
            "phenotype_count": len(self.phenotype_state),
            "drug_count": len(self.drug_context),
            "evidence_nodes": len(self.evidence_graph_nodes),
            "verification_nodes": len(self.verification_graph_nodes),
        }

    # ------------------------------------------------------------------
    # Annotated copies
    # ------------------------------------------------------------------

    def add_evidence_node(
        self,
        node: EvidenceNode,
        *,
        claim_id: str | None = None,
        relation: str = "supports",
        weight: float = 1.0,
    ) -> SharedBiomedicalContext:
        """Append an evidence node; optionally link to a claim."""
        nodes = (*self.evidence_graph_nodes, node)
        edges = self.evidence_graph_edges
        if claim_id is not None:
            edges = (
                *edges,
                EvidenceEdge(
                    claim_id=claim_id,
                    source_id=node.source_id,
                    relation=relation,
                    weight=weight,
                ),
            )
        return self.model_copy(
            update={
                "evidence_graph_nodes": nodes,
                "evidence_graph_edges": edges,
            }
        )

    def add_phenotype(
        self,
        state: PhenotypeState,
    ) -> SharedBiomedicalContext:
        return self.model_copy(update={"phenotype_state": (*self.phenotype_state, state)})

    def add_drug(
        self,
        drug: DrugContext,
    ) -> SharedBiomedicalContext:
        return self.model_copy(update={"drug_context": (*self.drug_context, drug)})

    def add_frequency(
        self,
        freq: AlleleFrequency,
    ) -> SharedBiomedicalContext:
        return self.model_copy(update={"allele_frequencies": (*self.allele_frequencies, freq)})

    def add_verdict(
        self,
        verdict: VerificationNode,
        *,
        link_to_claim: bool = True,
    ) -> SharedBiomedicalContext:
        """Append a verification node + optional claim edge."""
        nodes = (*self.verification_graph_nodes, verdict)
        edges = self.verification_graph_edges
        if link_to_claim:
            edges = (
                *edges,
                VerificationEdge(
                    claim_id=verdict.claim_id,
                    check_id=verdict.check_id,
                ),
            )
        return self.model_copy(
            update={
                "verification_graph_nodes": nodes,
                "verification_graph_edges": edges,
            }
        )

    # ------------------------------------------------------------------
    # Adapter
    # ------------------------------------------------------------------

    @classmethod
    def from_swarm_context(cls, ctx: Any) -> SharedBiomedicalContext:
        """Build a shared context from a ``SwarmExecutionContext``.

        Duck-typed so tests can pass a dict-shaped stub. Extracts
        the fields the 8 brief-named attributes cover; graphs start
        empty and are populated by specialist agents as they run.
        """

        def _get(attr: str, default: Any = None) -> Any:
            if isinstance(ctx, dict):
                return ctx.get(attr, default)
            return getattr(ctx, attr, default)

        workflow_id = _get("correlation_id") or _get("workflow_id") or ""
        population = _get("population") or ""
        genotype = dict(_get("genotype") or {})

        # Drug context: use the primary `drug` + any in `drugs` fan-out.
        drugs = []
        primary_drug = _get("drug")
        if primary_drug:
            drugs.append(DrugContext(drug=primary_drug))
        for d in _get("drugs") or []:
            if d != primary_drug:
                drugs.append(DrugContext(drug=d))

        return cls(
            workflow_id=workflow_id,
            population=population,
            genotype=genotype,
            drug_context=tuple(drugs),
        )


__all__ = [
    "SharedBiomedicalContext",
    "EvidenceNode",
    "EvidenceEdge",
    "VerificationNode",
    "VerificationEdge",
    "PhenotypeState",
    "DrugContext",
    "AlleleFrequency",
]
