"""``MCPEvidenceCache`` — indexed biomedical evidence cache.

Owns the ``evidence`` collection: one document per evidence passage
(CPIC guideline excerpt, PubMed abstract, drug-gene knowledge-base entry).

This is the read-side analog of ``retrieval/evidence/documents.py``:
that module *produces* passages for a single run, this service
*persists* them across runs so subsequent queries can hit the cache
instead of re-running retrieval.

Document shape (JSON-safe, populated by ``index``):

    {
      "_id":           <backend-assigned>,
      "source_id":     "PMID:34032273"        # primary key
      "gene":          "CYP2C19",
      "drug":          "clopidogrel",
      "population":    "SAS"                  # optional, many entries are pop-agnostic
      "title":         "Clopidogrel and CYP2C19 metabolizer status...",
      "content":       "<passage text>",
      "metadata":      { "year": 2022, "evidence_level": "strong", ... },
      "guideline_source": "CPIC",
      "indexed_at":    "2026-05-08T10:11:12+00:00"
    }

Tools:
  evidence.index       upsert a single passage (dedup by source_id)
  evidence.get         fetch one by source_id
  evidence.search      keyword+field filter (gene/drug/population/text)
  evidence.by_gene     all passages for a gene, newest first
  evidence.recent      N most recent indexed passages
  evidence.stats       coverage rollup (passages per gene, per source)

Search semantics
----------------
``evidence.search`` does field-equality filtering plus a case-insensitive
substring scan over ``title`` + ``content``. That covers every call site
in the swarm today. Upgrading to real text indexing (Mongo ``$text`` or
an external vector store) is a drop-in replacement behind this tool
name — callers stay on the MCP interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from integrations.mcp.client import MCPClient
from integrations.mcp.models import MCPOrigin, MCPToolResult


EVIDENCE_COLLECTION = "evidence"


@dataclass
class MCPEvidenceCache:
    """Persistent evidence cache with gene/drug/population indexing."""

    client: MCPClient
    collection: str = EVIDENCE_COLLECTION

    def __post_init__(self) -> None:
        self._register()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _register(self) -> None:
        r = self.client.registry
        r.register(
            "evidence.index",
            self._tool_index,
            description="Upsert one evidence passage (dedup by source_id).",
            origin=MCPOrigin.AGENT,
            override=True,
        )
        r.register(
            "evidence.get",
            self._tool_get,
            description="Fetch one evidence passage by source_id.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "evidence.search",
            self._tool_search,
            description=(
                "Keyword + field-filter search over indexed evidence; "
                "returns ranked passages."
            ),
            origin=MCPOrigin.AGENT,
            override=True,
        )
        r.register(
            "evidence.by_gene",
            self._tool_by_gene,
            description="All evidence passages for a gene, newest first.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "evidence.recent",
            self._tool_recent,
            description="N most recent indexed evidence passages.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )
        r.register(
            "evidence.stats",
            self._tool_stats,
            description="Coverage rollup — passages per gene, per guideline source.",
            origin=MCPOrigin.SYSTEM,
            override=True,
        )

    # ------------------------------------------------------------------
    # Python API
    # ------------------------------------------------------------------

    def index(
        self,
        *,
        source_id: str,
        content: str,
        gene: str = "",
        drug: str = "",
        population: str = "",
        title: str = "",
        guideline_source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MCPToolResult:
        """Upsert one passage (dedup by ``source_id``)."""
        return self.client.invoke(
            "evidence.index",
            args={
                "source_id": source_id,
                "content": content,
                "gene": gene,
                "drug": drug,
                "population": population,
                "title": title,
                "guideline_source": guideline_source,
                "metadata": metadata or {},
            },
            called_by="MCPEvidenceCache",
            origin=MCPOrigin.AGENT,
        )

    def get(self, source_id: str) -> MCPToolResult:
        return self.client.invoke(
            "evidence.get",
            args={"source_id": source_id},
            called_by="MCPEvidenceCache",
        )

    def search(
        self,
        query: str = "",
        *,
        gene: str = "",
        drug: str = "",
        population: str = "",
        limit: int = 10,
    ) -> MCPToolResult:
        return self.client.invoke(
            "evidence.search",
            args={
                "query": query,
                "gene": gene,
                "drug": drug,
                "population": population,
                "limit": limit,
            },
            called_by="MCPEvidenceCache",
        )

    def by_gene(self, gene: str, *, limit: int = 20) -> MCPToolResult:
        return self.client.invoke(
            "evidence.by_gene",
            args={"gene": gene, "limit": limit},
            called_by="MCPEvidenceCache",
        )

    def recent(self, limit: int = 10) -> MCPToolResult:
        return self.client.invoke(
            "evidence.recent",
            args={"limit": limit},
            called_by="MCPEvidenceCache",
        )

    def stats(self) -> MCPToolResult:
        return self.client.invoke(
            "evidence.stats",
            args={},
            called_by="MCPEvidenceCache",
        )

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def _tool_index(
        self,
        source_id: str,
        content: str,
        gene: str = "",
        drug: str = "",
        population: str = "",
        title: str = "",
        guideline_source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Upsert semantics: replace existing entry with the same ``source_id``."""
        if not source_id:
            raise ValueError("evidence.index requires source_id")
        if not content:
            raise ValueError("evidence.index requires non-empty content")

        # Remove any existing doc with this source_id so we don't
        # accumulate duplicates on re-index.
        try:
            self.client.backend.delete(self.collection, {"source_id": source_id})
        except Exception:
            # Some backends refuse empty filters; ours all accept this
            # filter shape, but any delete failure is non-fatal here —
            # worst case we end up with duplicates which ``get`` still
            # resolves deterministically (newest wins).
            pass

        doc = {
            "source_id": source_id,
            "content": content,
            "gene": gene,
            "drug": drug,
            "population": population,
            "title": title,
            "guideline_source": guideline_source,
            "metadata": dict(metadata or {}),
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }
        _id = self.client.backend.insert(self.collection, doc)
        return {"indexed": True, "_id": _id, "source_id": source_id}

    def _tool_get(self, source_id: str) -> dict[str, Any] | None:
        if not source_id:
            raise ValueError("evidence.get requires source_id")
        rows = self.client.backend.query(
            self.collection,
            {"source_id": source_id},
            sort=[("indexed_at", -1)],
            limit=1,
        )
        return rows[0] if rows else None

    def _tool_search(
        self,
        query: str = "",
        gene: str = "",
        drug: str = "",
        population: str = "",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Field filter first, then keyword scan, then rank by score."""
        filter_: dict[str, Any] = {}
        if gene:
            filter_["gene"] = gene
        if drug:
            filter_["drug"] = drug
        if population:
            filter_["population"] = population

        rows = self.client.backend.query(
            self.collection,
            filter_ or None,
            sort=[("indexed_at", -1)],
        )

        q = (query or "").strip().lower()
        if not q:
            return rows[: int(limit)]

        scored: list[tuple[int, dict[str, Any]]] = []
        for row in rows:
            hay = f"{row.get('title', '')} {row.get('content', '')}".lower()
            # Score = number of query-word occurrences. Simple but
            # deterministic and good enough for passage re-ranking.
            score = sum(hay.count(tok) for tok in q.split() if tok)
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [row for _, row in scored[: int(limit)]]

    def _tool_by_gene(
        self, gene: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        if not gene:
            raise ValueError("evidence.by_gene requires gene")
        return self.client.backend.query(
            self.collection,
            {"gene": gene},
            sort=[("indexed_at", -1)],
            limit=int(limit),
        )

    def _tool_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.client.backend.query(
            self.collection, None, sort=[("indexed_at", -1)], limit=int(limit)
        )

    def _tool_stats(self) -> dict[str, Any]:
        rows = self.client.backend.query(self.collection, None)
        by_gene: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_guideline: dict[str, int] = {}
        for r in rows:
            g = r.get("gene") or "—"
            s = r.get("guideline_source") or r.get("source_id", "—").split(":", 1)[0]
            gl = r.get("guideline_source") or "—"
            by_gene[g] = by_gene.get(g, 0) + 1
            by_source[s] = by_source.get(s, 0) + 1
            by_guideline[gl] = by_guideline.get(gl, 0) + 1
        return {
            "total": len(rows),
            "by_gene": by_gene,
            "by_source": by_source,
            "by_guideline": by_guideline,
        }


__all__ = ["MCPEvidenceCache", "EVIDENCE_COLLECTION"]
