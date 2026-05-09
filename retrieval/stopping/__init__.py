"""Retrieval stopping controller (phase 2 of the brief).

Implements the ECR / Stop-RAG / "Think Before You Fetch" idea:
stop retrieval once epistemic sufficiency is reached, and never
inflate retrieval beyond what the sufficiency layer actually needs.

Public surface (commit 8):

    StopSignal                    closed 3-value enum
                                  (STOP / FETCH_MORE / ABORT)
    RetrievalStoppingController   deterministic stopping policy —
                                  pure function of
                                  (SufficiencyReport, iteration,
                                   budget)

Deterministic: the decision is a pure function of the sufficiency
reading + budget state. No probabilities, no LLM.
"""

from __future__ import annotations

from retrieval.stopping.controller import (
    RetrievalStoppingController,
    StopSignal,
)

__all__ = ["RetrievalStoppingController", "StopSignal"]
