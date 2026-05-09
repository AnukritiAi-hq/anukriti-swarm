"""Evidence specialists — agent-facing façade for the sufficiency layer.

Contains agent-style wrappers that expose the deterministic classes
under ``core.evidence_sufficiency`` as swarm-compatible agents the
orchestrator can register and dispatch to via the existing agent bus
(``interoperability.AgentMessageBus``).

This package holds **no reasoning logic of its own**. It only
translates between the swarm's agent protocol and the deterministic
analyzers. Keep it thin.

Registered agents (after phase 1):

    ContextSufficiencyAgent   published as a first-class specialist
                              so the interoperability layer can
                              delegate sufficiency questions to it
                              the same way it delegates to
                              pharmacogene / population agents today
"""

from __future__ import annotations

__all__: list[str] = []
