"""Retrieval stopping controller (phase 2 of the brief).

Implements the ECR / Stop-RAG / "Think Before You Fetch" idea:
stop retrieval once epistemic sufficiency is reached, and never
inflate retrieval beyond what the sufficiency layer actually needs.

Single public class (added in phase 2):

    RetrievalStoppingController   inspects the current sufficiency
                                  reading and returns STOP / FETCH_MORE
                                  / ABORT. Bounded by an explicit budget
                                  so an underspecified query can never
                                  spin the retriever indefinitely.

Deterministic: the decision is a pure function of the sufficiency
reading + budget state. No probabilities, no LLM.
"""

from __future__ import annotations

__all__: list[str] = []
