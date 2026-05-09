"""``PharmacogenomicKnowledgeGraph`` — in-memory closed-schema graph.

Phase 3, commit 10 of the Evidence Sufficiency Layer brief.

A deterministic, closed-schema adjacency-list graph over the 10
``NodeKind`` values and 7 ``EdgeKind`` values defined in
``knowledge_graph.schema``. No external ontology imports, no LLM,
no embeddings. Lookup is O(1) by node id; outbound and inbound
adjacency are precomputed for fast traversal by the reasoner
(commit 11).

Scope firewall at every mutation
--------------------------------

    add_node    rejects unknown NodeKind (enum enforced at type),
                dedupes on Node.id (first-wins; idempotent re-add)
    add_edge    rejects unknown EdgeKind,
                rejects dangling source/target (both must already
                exist in the graph),
                rejects edges without a non-empty ProvenanceStamp
                source_id (the whole point of the schema)

Both mutators return the canonical in-graph instance (the existing
node/edge on re-add, the freshly-added one otherwise), so callers
can chain calls without tracking replacement state.

All query methods are **pure reads** — no mutation, no caching
that survives a mutation. Mutating the graph after a read simply
means the next read reflects the new state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator

from knowledge_graph.schema import (
    Edge,
    EdgeKind,
    Node,
    NodeKind,
    ProvenanceStamp,
)


def _edge_key(e: Edge) -> tuple[str, str, str, str]:
    """Deduplication key: same (src, kind, tgt, provenance) = same edge."""

    return (e.source_id, e.kind.value, e.target_id, e.stamp.source_id)


@dataclass
class PharmacogenomicKnowledgeGraph:
    """Closed-schema, in-memory KG over the brief's 10+7 kinds.

    Construction
    ------------
    Empty by default. Callers populate it via ``add_node`` /
    ``add_edge``, or use ``GraphContextBuilder.build_default()``
    (see below) to load the ``SEED_NODES`` / ``SEED_EDGES`` data.

    Internal state
    --------------
    ``_nodes``         node_id -> Node
    ``_out_edges``     source_id -> list[Edge] (outbound adjacency)
    ``_in_edges``      target_id -> list[Edge] (inbound adjacency)
    ``_edge_keys``     set of dedup keys so we don't store the same
                       (src, kind, tgt, source_id) twice

    All three index structures are always consistent; we update
    them atomically inside ``add_edge``.
    """

    _nodes: dict[str, Node] = field(default_factory=dict)
    _out_edges: dict[str, list[Edge]] = field(default_factory=dict)
    _in_edges: dict[str, list[Edge]] = field(default_factory=dict)
    _edge_keys: set[tuple[str, str, str, str]] = field(default_factory=set)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_node(self, node: Node) -> Node:
        """Insert ``node`` if absent; return the canonical in-graph Node."""

        if not isinstance(node.kind, NodeKind):  # defensive
            raise TypeError(
                f"node.kind must be NodeKind; got {type(node.kind).__name__}"
            )
        existing = self._nodes.get(node.id)
        if existing is not None:
            return existing
        self._nodes[node.id] = node
        # Touch adjacency lists to keep shapes consistent even when
        # there are no edges yet.
        self._out_edges.setdefault(node.id, [])
        self._in_edges.setdefault(node.id, [])
        return node

    def add_edge(self, edge: Edge) -> Edge:
        """Insert ``edge`` if absent; return the canonical in-graph Edge.

        Scope enforcement:
          - EdgeKind is enum-closed (rejected at type boundary).
          - Both endpoints must already be in the graph. No silent
            node creation — callers always add nodes explicitly.
          - ProvenanceStamp.source_id must be non-empty.
        """

        if not isinstance(edge.kind, EdgeKind):
            raise TypeError(
                f"edge.kind must be EdgeKind; got {type(edge.kind).__name__}"
            )
        if edge.source_id not in self._nodes:
            raise ValueError(
                f"edge source not in graph: {edge.source_id}"
            )
        if edge.target_id not in self._nodes:
            raise ValueError(
                f"edge target not in graph: {edge.target_id}"
            )
        if not isinstance(edge.stamp, ProvenanceStamp) or not edge.stamp.source_id:
            raise ValueError(
                "edge requires a ProvenanceStamp with a non-empty source_id"
            )

        key = _edge_key(edge)
        if key in self._edge_keys:
            # Find and return the existing canonical instance.
            for e in self._out_edges[edge.source_id]:
                if _edge_key(e) == key:
                    return e
        self._edge_keys.add(key)
        self._out_edges[edge.source_id].append(edge)
        self._in_edges[edge.target_id].append(edge)
        return edge

    def load(
        self,
        nodes: Iterable[Node],
        edges: Iterable[Edge],
    ) -> None:
        """Bulk-add nodes then edges (order matters for scope checks)."""

        for n in nodes:
            self.add_node(n)
        for e in edges:
            self.add_edge(e)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._nodes)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edge_keys)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_node(self, node_id: str) -> Node | None:
        return self._nodes.get(node_id)

    def nodes(self, *, kind: NodeKind | None = None) -> Iterator[Node]:
        """Iterate all nodes (optionally filtered by kind). Deterministic order."""

        for node_id in sorted(self._nodes):
            node = self._nodes[node_id]
            if kind is None or node.kind is kind:
                yield node

    def edges(
        self,
        *,
        kind: EdgeKind | None = None,
    ) -> Iterator[Edge]:
        """Iterate all edges (optionally filtered). Deterministic order."""

        # Flatten in node-id order then source-stable order within each.
        for src in sorted(self._out_edges):
            for e in self._out_edges[src]:
                if kind is None or e.kind is kind:
                    yield e

    def neighbors(
        self,
        node_id: str,
        *,
        kind: EdgeKind | None = None,
        direction: str = "out",
    ) -> list[Edge]:
        """Return edges incident to ``node_id`` (out / in / both).

        Deterministic: output order is the insertion order (stable).
        """

        if direction == "out":
            items = self._out_edges.get(node_id, [])
        elif direction == "in":
            items = self._in_edges.get(node_id, [])
        elif direction == "both":
            items = list(self._out_edges.get(node_id, [])) + list(
                self._in_edges.get(node_id, [])
            )
        else:
            raise ValueError(
                f"direction must be 'out' | 'in' | 'both'; got {direction!r}"
            )
        if kind is None:
            return list(items)
        return [e for e in items if e.kind is kind]

    def to_dict(self) -> dict:
        """Full JSON-safe dump — suitable for execution-trace persistence."""

        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "nodes": [self._nodes[nid].to_dict() for nid in sorted(self._nodes)],
            "edges": [e.to_dict() for e in self.edges()],
        }


__all__ = ["PharmacogenomicKnowledgeGraph"]
