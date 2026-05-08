"""Anukriti Swarm — Orchestrator package.

Two-tier orchestration:

1. ``OrchestratorAgent`` (this module, via ``agent.py``):
   Lightweight, deterministic graph node used as the first step of the
   LangGraph pipeline. Kept backward-compatible with prior imports::

       from agents.orchestrator import OrchestratorAgent

2. ``GeminiOrchestrator`` (via ``gemini_orchestrator.py``, added in a
   follow-up commit):
   High-level, Gemini-powered orchestration framework that composes
   planning, routing, coordination, context assembly, and narrative
   synthesis. Builds on ``core.orchestrator`` primitives.

Gemini is used **only** for planning and explanation. All biomedical
truth flows through the deterministic agents behind this orchestrator.
"""

from __future__ import annotations

from agents.orchestrator.agent import OrchestratorAgent

__all__ = ["OrchestratorAgent"]
