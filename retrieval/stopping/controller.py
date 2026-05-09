"""``RetrievalStoppingController`` — epistemic stopping policy.

Phase 2, commit 8 of the Evidence Sufficiency Layer brief.

Inspired by ECR / Stop-RAG / "Think Before You Fetch" — stop
retrieval once epistemic sufficiency is reached, and never inflate
retrieval beyond what the sufficiency layer actually needs.

A single public class with one method:

    decide(report: SufficiencyReport, iteration: int, *, budget: int)
        -> StopSignal

The decision is a pure function of the report's
``SufficiencyDecision`` + the iteration budget. No probabilities,
no LLM, no randomness. Two identical inputs always produce the
same signal.

Three signals (closed set)
--------------------------

    STOP          a terminal decision has been reached; the adaptive
                  loop should return the current report as final.
                  Fires on SUFFICIENT / PASS_WITH_CAVEAT / DOWNGRADE
                  / BLOCK / ABSTAIN / ESCALATE — any of the 6
                  non-addressable decisions.

    FETCH_MORE    the decision is REQUEST_MORE *and* iteration <
                  budget. The loop should broaden retrieval and
                  re-evaluate.

    ABORT         iteration has reached budget while the decision is
                  still REQUEST_MORE. The loop must give up cleanly
                  with the last report rather than spin forever.

Why ABORT as a separate signal (not just STOP)?
  ABORT carries *distinct audit semantics*: the run ended without
  finding enough evidence despite a finite number of retrieval
  rounds. STOP means "the layer decided"; ABORT means "the loop
  ran out of time". The AdaptiveRetrievalController stamps
  budget_exhausted=True on the final report only on ABORT.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.evidence_sufficiency.sufficiency.decision_engine import (
    SufficiencyDecision,
    SufficiencyReport,
)


class StopSignal(str, Enum):
    """Closed-enum stopping signal — extending is a code change."""

    STOP = "stop"
    FETCH_MORE = "fetch_more"
    ABORT = "abort"


@dataclass
class RetrievalStoppingController:
    """Deterministic stopping policy.

    Stateless. One instance serves many loops.

    Configuration
    -------------
    No configuration. The mapping from SufficiencyDecision to
    StopSignal is fixed. The budget is passed at the ``decide`` call
    site so a caller running a retrieval loop can express "give me
    5 rounds for this query" without mutating the controller.
    """

    def decide(
        self,
        report: SufficiencyReport,
        iteration: int,
        *,
        budget: int,
    ) -> StopSignal:
        """Return STOP / FETCH_MORE / ABORT based on the report + budget.

        ``iteration`` is the 0-based index of the round that
        *produced* ``report``. Budget is the maximum number of
        rounds the caller is willing to run. Beyond
        ``iteration >= budget - 1`` the controller refuses to
        recommend another round even when the decision is
        REQUEST_MORE — that's ABORT.
        """

        if report.decision is SufficiencyDecision.REQUEST_MORE:
            if iteration < budget - 1:
                return StopSignal.FETCH_MORE
            return StopSignal.ABORT
        # Every other decision is terminal for the loop.
        return StopSignal.STOP


__all__ = ["StopSignal", "RetrievalStoppingController"]
