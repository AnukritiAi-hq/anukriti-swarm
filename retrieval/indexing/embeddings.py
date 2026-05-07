"""Embedding abstraction and vector index.

Provides a lightweight vector index using keyword-based similarity
(TF-IDF style) for mock retrieval. The abstraction layer allows
swapping to real embedding models (OpenAI, sentence-transformers)
without changing retrieval logic.

Future:
- MCP Retrieval server with Qdrant backend
- Real embedding models (text-embedding-3-small)
- ScaleMCP for distributed vector search
- Dynamic tool discovery for new indexes
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from retrieval.evidence.documents import ALL_DOCUMENTS, BiomedicalDocument


@dataclass
class IndexEntry:
    """A document indexed with its term frequencies."""

    doc: BiomedicalDocument
    terms: Counter = field(default_factory=Counter)


class VectorIndex:
    """Keyword-based vector index (mock embedding layer).

    Uses TF-IDF-style scoring for document retrieval. This provides
    deterministic, reproducible retrieval without requiring an
    embedding model or external service.

    Interface is designed to be swappable with real vector stores:
    - index(documents): build index
    - search(query, top_k): retrieve ranked results
    - similarity(query, doc): compute relevance score

    Future: Replace internals with Qdrant client or MCP retrieval calls.
    """

    def __init__(self) -> None:
        self._entries: list[IndexEntry] = []
        self._doc_count = 0
        self._idf: dict[str, float] = {}

    def index(self, documents: list[BiomedicalDocument] | None = None) -> None:
        """Build index from documents."""
        docs = documents or ALL_DOCUMENTS
        self._entries = []

        for doc in docs:
            terms = self._tokenize(doc)
            self._entries.append(IndexEntry(doc=doc, terms=terms))

        self._doc_count = len(self._entries)
        self._compute_idf()

    def search(self, query: str, top_k: int = 5, gene_filter: str | None = None, drug_filter: str | None = None) -> list[tuple[BiomedicalDocument, float]]:
        """Search index and return ranked (document, score) pairs."""
        if not self._entries:
            self.index()

        query_terms = self._tokenize_text(query)
        results: list[tuple[BiomedicalDocument, float]] = []

        for entry in self._entries:
            # Apply filters
            if gene_filter and gene_filter not in entry.doc.genes:
                continue
            if drug_filter and drug_filter not in entry.doc.drugs:
                continue

            score = self._score(query_terms, entry)
            if score > 0:
                results.append((entry.doc, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _score(self, query_terms: Counter, entry: IndexEntry) -> float:
        """TF-IDF cosine similarity approximation."""
        score = 0.0
        for term, query_tf in query_terms.items():
            doc_tf = entry.terms.get(term, 0)
            idf = self._idf.get(term, 0.0)
            score += query_tf * doc_tf * idf
        return score

    def _compute_idf(self) -> None:
        """Compute inverse document frequency for all terms."""
        doc_freq: Counter = Counter()
        for entry in self._entries:
            for term in set(entry.terms.keys()):
                doc_freq[term] += 1

        self._idf = {
            term: math.log(self._doc_count / (1 + df))
            for term, df in doc_freq.items()
        }

    def _tokenize(self, doc: BiomedicalDocument) -> Counter:
        """Tokenize a document into term frequencies."""
        text = f"{doc.title} {doc.content} {' '.join(doc.keywords)} {' '.join(doc.genes)} {' '.join(doc.drugs)}"
        return self._tokenize_text(text)

    def _tokenize_text(self, text: str) -> Counter:
        """Simple whitespace + lowercase tokenization."""
        tokens = text.lower().replace(",", " ").replace(".", " ").replace("(", " ").replace(")", " ").split()
        return Counter(t for t in tokens if len(t) > 2)
