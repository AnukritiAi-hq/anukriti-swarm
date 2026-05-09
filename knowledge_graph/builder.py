"""``GraphContextBuilder`` + ``PopulationGraphIndexer``.

Phase 3, commit 10 of the Evidence Sufficiency Layer brief.

GraphContextBuilder
-------------------
Tiny factory — turns the closed seed data (``SEED_NODES`` +
``SEED_EDGES``, commit 9) into a populated
``PharmacogenomicKnowledgeGraph``. Separate from the graph class so
the graph stays pure (construction has no implicit seed load), and
so tests can spin up empty or custom-seeded graphs without monkey
patches.

PopulationGraphIndexer
----------------------
Population is a **first-class reasoning dimension**, not metadata.
This indexer pre-computes three population-keyed lookups the
reasoner (commit 11) and retriever consumers use directly:

    alleles_by_population   SuperPopulation -> sorted list of
                            (allele_node, frequency) tuples,
                            descending by frequency
    drugs_by_population     SuperPopulation -> sorted list of
                            drug Nodes whose *allele path* is
                            observed in that population (via
                            CONTRAINDICATED_FOR or
                            ASSOCIATED_WITH)
    evidence_by_population  SuperPopulation -> sorted tuple of
                            EVIDENCE_PAPER ids that support any
                            allele observed in that population
                            (via SUPPORTED_BY)

All three are derived deterministically from the graph state at
index-time. Mutating the graph invalidates the indexer; callers
must rebuild (``PopulationGraphIndexer.build(graph)``) to see new
data — same contract as a SQL index.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Mapping

from core.models.population import SuperPopulation
from knowledge_graph.graph import PharmacogenomicKnowledgeGraph
from knowledge_graph.schema import EdgeKind, Node, NodeKind
from knowledge_graph.seed import SEED_EDGES, SEED_NODES


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


@dataclass
class GraphContextBuilder:
    """Factory producing populated ``PharmacogenomicKnowledgeGraph``s."""

    def build_empty(self) -> PharmacogenomicKnowledgeGraph:
        """A brand-new empty graph. Useful for focused tests."""

        return PharmacogenomicKnowledgeGraph()

    def build_default(self) -> PharmacogenomicKnowledgeGraph:
        """Load ``SEED_NODES`` + ``SEED_EDGES`` into a new graph.

        Deterministic: every call with no arguments produces a
        structurally-identical graph (modulo node/edge dataclass
        timestamps, which the tests strip before comparison).
        """

        graph = PharmacogenomicKnowledgeGraph()
        graph.load(SEED_NODES, SEED_EDGES)
        return graph


# ---------------------------------------------------------------------------
# Indexer
# ---------------------------------------------------------------------------


def _population_from_node(node: Node) -> SuperPopulation | None:
    """Map a POPULATION node to a SuperPopulation enum instance.

    Seed population names match the enum values ('SAS', 'EAS', etc.)
    so the lookup is exact. Anything that doesn't parse -> None and
    the indexer ignores it. Unknown super-population codes are
    impossible in seed, but we defensively skip rather than raise.
    """

    if node.kind is not NodeKind.POPULATION:
        return None
    try:
        return SuperPopulation(node.name.strip().upper())
    except ValueError:
        return None


@dataclass
class PopulationGraphIndexer:
    """Deterministic population-keyed indexer over a KG.

    Instances are produced via ``PopulationGraphIndexer.build(graph)``.
    The class itself holds no state; the returned instance holds the
    three derived indices and the timestamp the graph was read at.

    Queries are O(1) lookups; the heavy work happens once in ``build``.
    """

    alleles_by_population: Mapping[
        SuperPopulation, tuple[tuple[Node, float], ...]
    ] = field(default_factory=dict)
    drugs_by_population: Mapping[
        SuperPopulation, tuple[Node, ...]
    ] = field(default_factory=dict)
    evidence_by_population: Mapping[
        SuperPopulation, tuple[str, ...]
    ] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def build(
        cls, graph: PharmacogenomicKnowledgeGraph
    ) -> "PopulationGraphIndexer":
        """Scan ``graph`` once; return a fully-populated indexer."""

        alleles_acc: dict[
            SuperPopulation, list[tuple[Node, float]]
        ] = defaultdict(list)
        drugs_acc: dict[SuperPopulation, list[Node]] = defaultdict(list)
        evidence_acc: dict[SuperPopulation, list[str]] = defaultdict(list)

        # --- Pass 1: HIGHER_FREQUENCY_IN edges drive everything.
        # allele -> (pop, freq).
        allele_to_pops: dict[str, list[tuple[SuperPopulation, float]]] = (
            defaultdict(list)
        )
        for edge in graph.edges(kind=EdgeKind.HIGHER_FREQUENCY_IN):
            source = graph.get_node(edge.source_id)
            target = graph.get_node(edge.target_id)
            if source is None or target is None:
                continue
            if source.kind is not NodeKind.ALLELE:
                continue
            pop = _population_from_node(target)
            if pop is None:
                continue
            alleles_acc[pop].append((source, float(edge.weight)))
            allele_to_pops[source.id].append((pop, float(edge.weight)))

        # --- Pass 2: drugs reachable from alleles via contraindicated_for
        # or associated_with. An allele -> drug link exists when:
        #   allele -[contra]-> drug directly
        #   allele -[contra]-> phenotype  (none in seed; skipped by kind check)
        #   drug is in ASSOCIATED_WITH relation starting from allele's
        #   phenotype — we follow CONTRA from any phenotype that shares
        #   the allele's gene (payload['gene']).
        for allele_id, pops in allele_to_pops.items():
            drugs_reached = cls._drugs_reachable_from_allele(graph, allele_id)
            for pop, _ in pops:
                for drug in drugs_reached:
                    drugs_acc[pop].append(drug)

        # --- Pass 3: evidence supporting any allele observed in population.
        for allele_id, pops in allele_to_pops.items():
            for support_edge in graph.neighbors(
                allele_id, kind=EdgeKind.SUPPORTED_BY, direction="out"
            ):
                ev_node = graph.get_node(support_edge.target_id)
                if ev_node is None or ev_node.kind is not NodeKind.EVIDENCE_PAPER:
                    continue
                for pop, _ in pops:
                    evidence_acc[pop].append(ev_node.name)

        # --- Finalise: sort deterministically and freeze into tuples.
        alleles_final: dict[SuperPopulation, tuple[tuple[Node, float], ...]] = {}
        for pop, pairs in alleles_acc.items():
            # Sort by frequency desc, then by allele id asc for stability.
            pairs.sort(key=lambda ab: (-ab[1], ab[0].id))
            alleles_final[pop] = tuple(pairs)

        drugs_final: dict[SuperPopulation, tuple[Node, ...]] = {}
        for pop, drugs in drugs_acc.items():
            # Dedup by id, sort alphabetically for stable output.
            seen: set[str] = set()
            deduped: list[Node] = []
            for d in drugs:
                if d.id in seen:
                    continue
                seen.add(d.id)
                deduped.append(d)
            deduped.sort(key=lambda n: n.id)
            drugs_final[pop] = tuple(deduped)

        evidence_final: dict[SuperPopulation, tuple[str, ...]] = {}
        for pop, ev_ids in evidence_acc.items():
            evidence_final[pop] = tuple(sorted(set(ev_ids)))

        return cls(
            alleles_by_population=alleles_final,
            drugs_by_population=drugs_final,
            evidence_by_population=evidence_final,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _drugs_reachable_from_allele(
        graph: PharmacogenomicKnowledgeGraph,
        allele_id: str,
    ) -> list[Node]:
        """Follow allele -> {contra | assoc} -> drug, 1-2 hops.

        Covers two patterns in the seed:
          direct:       ALLELE --[CONTRAINDICATED_FOR]--> DRUG
                        (HLA-B*15:02 -> carbamazepine)
          via phenotype: ALLELE -> (no direct edge; however the
                        allele's gene has phenotypes that connect to
                        drugs via CONTRAINDICATED_FOR). We look up
                        phenotypes sharing the allele's gene payload
                        and follow their CONTRA edges.
        """

        drugs: list[Node] = []

        allele_node = graph.get_node(allele_id)
        if allele_node is None:
            return drugs
        allele_gene = allele_node.payload.get("gene")

        # Direct.
        for e in graph.neighbors(
            allele_id, kind=EdgeKind.CONTRAINDICATED_FOR, direction="out"
        ):
            tgt = graph.get_node(e.target_id)
            if tgt is not None and tgt.kind is NodeKind.DRUG:
                drugs.append(tgt)

        # Indirect via phenotype (phenotype.payload['gene'] == allele's gene).
        if allele_gene:
            for pheno in graph.nodes(kind=NodeKind.PHENOTYPE):
                if pheno.payload.get("gene") != allele_gene:
                    continue
                for e in graph.neighbors(
                    pheno.id, kind=EdgeKind.CONTRAINDICATED_FOR, direction="out"
                ):
                    tgt = graph.get_node(e.target_id)
                    if tgt is not None and tgt.kind is NodeKind.DRUG:
                        drugs.append(tgt)

        return drugs

    # ------------------------------------------------------------------
    # Query façade
    # ------------------------------------------------------------------

    def alleles_for(
        self, population: SuperPopulation, *, min_frequency: float = 0.0
    ) -> tuple[tuple[Node, float], ...]:
        """Return sorted (allele, frequency) pairs for ``population``.

        Empty tuple if the population has no observed alleles.
        """

        pairs = self.alleles_by_population.get(population, ())
        if min_frequency <= 0.0:
            return pairs
        return tuple(p for p in pairs if p[1] >= min_frequency)

    def drugs_for(self, population: SuperPopulation) -> tuple[Node, ...]:
        return self.drugs_by_population.get(population, ())

    def evidence_for(self, population: SuperPopulation) -> tuple[str, ...]:
        return self.evidence_by_population.get(population, ())

    def to_dict(self) -> dict:
        return {
            "alleles_by_population": {
                pop.value: [
                    {"allele_id": node.id, "frequency": round(freq, 4)}
                    for node, freq in pairs
                ]
                for pop, pairs in self.alleles_by_population.items()
            },
            "drugs_by_population": {
                pop.value: [n.id for n in drugs]
                for pop, drugs in self.drugs_by_population.items()
            },
            "evidence_by_population": {
                pop.value: list(ev_ids)
                for pop, ev_ids in self.evidence_by_population.items()
            },
        }


__all__ = ["GraphContextBuilder", "PopulationGraphIndexer"]
