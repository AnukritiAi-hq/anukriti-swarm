"""Anukriti Swarm — Orchestrator package.

Two-tier orchestration:

1. ``OrchestratorAgent`` (this module, via ``agent.py``):
   Lightweight, deterministic graph node used as the first step of the
   LangGraph pipeline. Kept backward-compatible with prior imports::

       from agents.orchestrator import OrchestratorAgent

2. ``GeminiOrchestrator`` (via ``gemini_orchestrator.py``):
   High-level, Gemini-powered orchestration framework that composes
   planning, routing, coordination, context assembly, and narrative
   synthesis. Builds on ``core.orchestrator`` primitives::

       from agents.orchestrator import GeminiOrchestrator
       result = GeminiOrchestrator().run(
           gene="CYP2C19", drug="clopidogrel", population="SAS",
           allele1="*2", allele2="*2",
       )

Gemini is used **only** for planning and explanation. All biomedical
truth flows through the deterministic agents behind this orchestrator.

Import rules
------------
``OrchestratorAgent`` is re-exported eagerly because the top-level
``agents`` package re-exports it (keeping the long-standing
``from agents import OrchestratorAgent`` working).

``GeminiOrchestrator`` is **lazy** because importing it pulls in
``core.orchestrator.coordinator`` which itself imports from ``agents.*``
(via the registry catalog). Eager re-export here would create a
circular import during ``agents/__init__.py`` load.

The ``__getattr__`` hook below means
``from agents.orchestrator import GeminiOrchestrator`` still works for
users — the import is just performed on first access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agents.orchestrator.agent import OrchestratorAgent

if TYPE_CHECKING:  # pragma: no cover — type-checker view only
    from agents.orchestrator.gemini_orchestrator import (
        GeminiOrchestrator,
        OrchestrationResult,
    )

__all__ = [
    "OrchestratorAgent",
    "GeminiOrchestrator",
    "OrchestrationResult",
]


def __getattr__(name: str) -> Any:
    """Lazy re-export to avoid importing the Gemini stack at package load.

    PEP 562 — module-level ``__getattr__``. Executed only when an
    attribute isn't found statically on the module, so ``OrchestratorAgent``
    (eager) has zero cost overhead.
    """
    if name in ("GeminiOrchestrator", "OrchestrationResult"):
        from agents.orchestrator import gemini_orchestrator as _mod

        value = getattr(_mod, name)
        globals()[name] = value  # cache for future lookups
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
