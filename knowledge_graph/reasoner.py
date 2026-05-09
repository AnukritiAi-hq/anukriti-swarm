"""``MultiHopReasoner`` + ``PathEvidenceRetriever``.

Phase 3, commit 11 of the Evidence Sufficiency Layer brief.

Final phase-3 component. Turns a populated
``PharmacogenomicKnowledgeGraph`` into an active reasoning surface:

    MultiHopReasoner        bounded BFS over the graph; returns
                            GraphPaths with population-aware weights
                            and conflict awareness
    PathEvidenceRetriever   walks a bundle of GraphPaths and emits
                            ``RetrievedEvidence`` entries ready for
                            the ``RetrievalStrategyResult`` surface
                            consumed by phase 2

Deterministic, LLM-free. Bounded-depth BFS (default ``max_hops=4``)
per brief req #11. Population-aware traversal per req #12 — when a
target super-population is supplied, the reasoner:

    * weights each path by the product of HIGHER_FREQUENCY_IN edge
      weights along the path (default 1.0 if no frequency edge is
      touched — the path is population-neutral)
    * optionally prunes paths that touch alleles not observed above
      a frequency floor in the target population (avoids reasoning
      about alleles that effectively do not exist in that ancestry)

Conflict-aware traversal: CONFLICTS_WITH edges are never crossed by
BFS — two conflicting evidence nodes do not form a traversable path.

Paths are frozen. The bundle the reasoner returns is deterministic
across runs: sorted by (hop_count asc, -population_weight desc,
start_id asc, tuple-of-edge-keys asc) so repeat queries produce
byte-identical path bundles.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from core.models.population import SuperPopulation
from knowledge_graph.builder import PopulationGraphIndexer
from knowledge_graph.graph import PharmacogenomicKnowledgeGraph
from knowledge_graph.schema import Edge, EdgeKind, Node, NodeKind
from retrieval.evidence.documents import DocumentSource
from retrieval.evidence.retriever import Citation, RetrievedEvidence


# ---------------------------------------------------------------------------
# GraphPath — frozen audit record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GraphPath:
    """Frozen reasoning path across the KG.

    Fields
    ------
    nodes                tuple of Node, length = hops + 1
    edges                tuple of Edge, length = hops; edges[i]
                         connects nodes[i] to nodes[i+1]
    population_weight    product of HIGHER_FREQUENCY_IN edge weights
                         along the path for the target population;
                         1.0 if no frequency edge touches the path
                         (population-neutral)
    evidence_refs        tuple of EVIDENCE_PAPER node names touched
                         along the path (via SUPPORTED_BY edges),
                         sorted lexically for stability
    """

    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    population_weight: float = 1.0
    evidence_refs: tuple[str, ...] = ()

    @property
    def hop_count(self) -> int:
        return len(self.edges)

    @property
    def start(self) -> Node:
        return self.nodes[0]

    @property
    def end(self) -> Node:
        return self.nodes[-1]

    def contains_population(self, pop: SuperPopulation) -> bool:
        """True iff the path touches ``pop`` as a node."""

        return any(
            n.kind is NodeKind.POPULATION and n.name == pop.value
            for n in self.nodes
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hop_count": self.hop_count,
            "start_id": self.start.id,
            "end_id": self.end.id,
            "population_weight": round(float(self.population_weight), 6),
            "nodes": [n.id for n in self.nodes],
            "edges": [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "kind": e.kind.value,
                    "weight": round(float(e.weight), 4),
                    "source_id_stamp": e.stamp.source_id,
                }
                for e in self.edges
            ],
            "evidence_refs": list(self.evidence_refs),
        }


# ---------------------------------------------------------------------------
# MultiHopReasoner
# ---------------------------------------------------------------------------


@dataclass
class MultiHopReasoner:
    """Bounded-BFS reasoner over the pharmacogenomic KG.

    Stateless. One instance handles many queries.

    Options
    -------
    max_hops          default 4 — hard ceiling per brief req #11.
                      Each path uses ≤ max_hops edges.
    min_pop_frequency default 0.0 — floor for population-aware
                      pruning. When target_population is supplied
                      and an ALLELE node is visited, the edge
                      HIGHER_FREQUENCY_IN the target-population is
                      checked; alleles with freq < floor get their
                      path rejected. 0.0 disables pruning (all
                      paths allowed; population_weight still
                      computed).
    skip_conflicts    default True — CONFLICTS_WITH edges are never
                      traversed. Set False only for introspection.
    """

    max_hops: int = 4
    min_pop_frequency: float = 0.0
    skip_conflicts: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_paths(
        self,
        graph: PharmacogenomicKnowledgeGraph,
        start_id: str,
        goal_id: str,
        *,
        target_population: SuperPopulation | None = None,
        pop_indexer: PopulationGraphIndexer | None = None,
    ) -> tuple[GraphPath, ...]:
        """BFS over ``graph`` from ``start_id`` to ``goal_id``.

        Returns all paths of length ≤ ``max_hops`` that satisfy the
        population-aware filters. Empty tuple if start or goal is
        missing or if no path exists within the budget.
        """

        if start_id not in graph._nodes or goal_id not in graph._nodes:
            return ()

        start_node = graph.get_node(start_id)
        goal_node = graph.get_node(goal_id)
        if start_node is None or goal_node is None:
            return ()

        pop_lookup: dict[str, float] | None = None
        if target_population is not None and pop_indexer is not None:
            pop_lookup = {
                node.id: freq
                for node, freq in pop_indexer.alleles_for(target_population)
            }

        paths: list[GraphPath] = []

        # Queue entries are (current_node_id, nodes_tuple, edges_tuple,
        # visited_set, pop_weight).
        queue: deque[tuple[str, tuple[Node, ...], tuple[Edge, ...], set[str], float]] = deque()
        queue.append((
            start_id,
            (start_node,),
            (),
            {start_id},
            1.0,
        ))

        while queue:
            current_id, nodes_tuple, edges_tuple, visited, weight = queue.popleft()

            if current_id == goal_id and len(edges_tuple) > 0:
                paths.append(self._freeze_path(nodes_tuple, edges_tuple, weight))
                # Continue exploring: different routes to the goal are
                # separate paths worth surfacing.
                continue

            if len(edges_tuple) >= self.max_hops:
                continue

            for edge in graph.neighbors(current_id, direction="out"):
                if self.skip_conflicts and edge.kind is EdgeKind.CONFLICTS_WITH:
                    continue
                next_id = edge.target_id
                if next_id in visited:
                    continue  # no cycles
                next_node = graph.get_node(next_id)
                if next_node is None:
                    continue

                # Population-aware pruning: if the next node is an
                # ALLELE and a target population + floor are set,
                # require the allele to clear the floor.
                if (
                    pop_lookup is not None
                    and next_node.kind is NodeKind.ALLELE
                    and self.min_pop_frequency > 0.0
                ):
                    if pop_lookup.get(next_node.id, 0.0) < self.min_pop_frequency:
                        continue

                # Accumulate population weight on HIGHER_FREQUENCY_IN
                # edges that target the population of interest.
                new_weight = weight
                if (
                    target_population is not None
                    and edge.kind is EdgeKind.HIGHER_FREQUENCY_IN
                    and next_node.kind is NodeKind.POPULATION
                    and next_node.name == target_population.value
                ):
                    new_weight *= float(edge.weight)

                queue.append((
                    next_id,
                    nodes_tuple + (next_node,),
                    edges_tuple + (edge,),
                    visited | {next_id},
                    new_weight,
                ))

        # Deterministic sort.
        paths.sort(
            key=lambda p: (
                p.hop_count,
                -p.population_weight,
                p.start.id,
                tuple((e.source_id, e.kind.value, e.target_id, e.stamp.source_id)
                      for e in p.edges),
            )
        )
        return tuple(paths)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _freeze_path(
        nodes: tuple[Node, ...],
        edges: tuple[Edge, ...],
        weight: float,
    ) -> GraphPath:
        """Build a frozen ``GraphPath`` with evidence_refs extracted."""

        ev_ids: list[str] = []
        for node in nodes:
            if node.kind is NodeKind.EVIDENCE_PAPER:
                ev_ids.append(node.name)
        return GraphPath(
            nodes=nodes,
            edges=edges,
            population_weight=round(float(weight), 6),
            evidence_refs=tuple(sorted(set(ev_ids))),
        )


# ---------------------------------------------------------------------------
# PathEvidenceRetriever
# ---------------------------------------------------------------------------


def _citation_source_from_stamp(source_type: str) -> DocumentSource:
    """Map a stamp.source_type to a DocumentSource (best-effort)."""

    mapping = {
        "cpic": DocumentSource.CPIC,
        "pharmgkb": DocumentSource.PHARMGKB,
        "pubmed": DocumentSource.PUBMED,
    }
    return mapping.get(source_type, DocumentSource.PUBMED)


@dataclass
class PathEvidenceRetriever:
    """Convert a bundle of ``GraphPath`` into ``RetrievedEvidence``.

    The output shape matches ``retrieval.evidence.retriever.RetrievedEvidence``
    so it plugs into the existing ``RetrievalResult`` / selector /
    sufficiency pipeline without adaptation.

    One ``RetrievedEvidence`` entry per unique ``EVIDENCE_PAPER``
    node visited anywhere in the bundle. The relevance score is a
    deterministic function of the evidence's best population_weight
    across paths that touched it — higher pop-aligned paths surface
    the evidence more strongly.

    Scope firewall
    --------------
    The retriever consumes only EVIDENCE_PAPER nodes off the paths;
    it does not invent new entries, does not touch the graph
    further, and does not reach into the document corpus. It
    synthesizes citations from the node's payload + stamp only.
    """

    # Base relevance score assigned before population-weight modulation.
    # Keeps the output in the same rough numeric range as the dense
    # retriever (scores around 3-6 for in-seed docs).
    base_score: float = 3.0
    # How much the population_weight (0..1) scales into extra score.
    pop_weight_scale: float = 2.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def retrieve_from_paths(
        self,
        graph: PharmacogenomicKnowledgeGraph,
        paths: tuple[GraphPath, ...],
        *,
        intent: str = "graph_multi_hop",
    ) -> list[RetrievedEvidence]:
        """Build RetrievedEvidence entries keyed on the paths' evidence."""

        # Collect best (max) population_weight across paths per evidence id.
        best_weight: dict[str, float] = {}
        gene_drug_on_path: dict[str, tuple[str | None, str | None]] = {}
        for path in paths:
            genes_on_path = [
                n.name for n in path.nodes if n.kind is NodeKind.GENE
            ]
            drugs_on_path = [
                n.name for n in path.nodes if n.kind is NodeKind.DRUG
            ]
            first_gene = genes_on_path[0] if genes_on_path else None
            first_drug = drugs_on_path[0] if drugs_on_path else None
            for ev_id in path.evidence_refs:
                existing = best_weight.get(ev_id, -1.0)
                if path.population_weight > existing:
                    best_weight[ev_id] = path.population_weight
                    gene_drug_on_path[ev_id] = (first_gene, first_drug)

        evidence: list[RetrievedEvidence] = []
        for ev_id, weight in best_weight.items():
            node = graph.get_node(f"evidence_paper:{ev_id}")
            if node is None:
                continue
            citation = self._build_citation(node)
            if citation is None:
                continue
            gene, drug = gene_drug_on_path.get(ev_id, (None, None))
            score = round(
                float(self.base_score) + float(self.pop_weight_scale) * float(weight),
                4,
            )
            evidence.append(
                RetrievedEvidence(
                    evidence_id=f"ev_graph_{ev_id}",
                    content=str(node.payload.get("title", ev_id)),
                    citation=citation,
                    relevance_score=score,
                    gene=gene,
                    drug=drug,
                    sub_query_id="graph",
                    intent=intent,
                    retrieval_method="graph_multi_hop",
                )
            )
        # Deterministic ordering: desc score, asc citation_id.
        evidence.sort(key=lambda e: (-e.relevance_score, e.citation.citation_id))
        return evidence

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _build_citation(node: Node) -> Citation | None:
        """Synthesize a Citation from an EVIDENCE_PAPER node.

        Defensive — if the node lacks a stamp or essential payload
        we return None rather than fabricate.
        """

        if node.kind is not NodeKind.EVIDENCE_PAPER or node.stamp is None:
            return None
        return Citation(
            citation_id=node.name,
            source=_citation_source_from_stamp(node.stamp.source_type),
            title=str(node.payload.get("title", node.name)),
            year=int(node.payload.get("year", 0)),
        )


__all__ = [
    "GraphPath",
    "MultiHopReasoner",
    "PathEvidenceRetriever",
]
