"""Evidence Sufficiency — ``sufficiency/`` subpackage.

Hosts the decision-layer classes that decide *what to do* with a
coverage + conflict + uncertainty reading:

    SufficiencyDecision         closed 7-value enum (commit 5)
    SufficiencyReport           frozen per-run decision record
                                (commit 5)
    SufficiencyDecisionEngine   pure 12-rule policy engine
                                (commit 5)
    ContextSufficiencyAgent     orchestration-facing wrapper that
                                composes the analyzer + conflict
                                detector + provenance tracker +
                                engine into a single ``evaluate``
                                call (commit 5)

Both are deterministic. The agent does no generative reasoning
itself — it reads facets, relation strength, and conflict sets
produced by the analyzers in ``coverage/`` and ``conflict/``.
"""

from __future__ import annotations

from core.evidence_sufficiency.sufficiency.context_agent import (
    ContextSufficiencyAgent,
)
from core.evidence_sufficiency.sufficiency.decision_engine import (
    SufficiencyDecision,
    SufficiencyDecisionEngine,
    SufficiencyReport,
)

__all__ = [
    "ContextSufficiencyAgent",
    "SufficiencyDecision",
    "SufficiencyDecisionEngine",
    "SufficiencyReport",
]
