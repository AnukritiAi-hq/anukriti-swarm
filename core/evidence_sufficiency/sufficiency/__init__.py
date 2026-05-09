"""Evidence Sufficiency — ``sufficiency/`` subpackage.

Hosts the decision-layer classes that decide *what to do* with a
coverage + conflict + uncertainty reading:

    SufficiencyDecisionEngine   pure policy: map (coverage, conflicts,
                                uncertainty) → {sufficient, request_more,
                                block, escalate, downgrade, abstain, pass}
    ContextSufficiencyAgent     orchestration-facing wrapper that gathers
                                inputs from the existing verification +
                                retrieval stacks and calls the engine

Both are deterministic. The agent does no generative reasoning
itself — it reads facets, relation strength, and conflict sets
produced by the analyzers in ``coverage/`` and ``conflict/``.
"""

from __future__ import annotations

__all__: list[str] = []
