"""Anukriti Swarm — Orchestration framework primitives.

This package contains the **reusable orchestration framework** that the
Gemini-powered ``GeminiOrchestrator`` (in ``agents.orchestrator``) is built
on top of. The split follows the project's deterministic/generative
boundary:

- ``core.orchestrator`` — deterministic framework (context, trace, routing,
  coordination, safety boundary). No LLM calls happen here directly.
- ``agents.orchestrator.gemini_orchestrator`` — high-level orchestrator that
  uses an ``AIClient`` for *planning and synthesis only*, delegating all
  biomedical reasoning to deterministic agents via this framework.

Modules (added in follow-up commits):

- ``context``            — ``SwarmExecutionContext`` (shared state model)
- ``trace``              — ``OrchestrationTrace``, ``ActivationLog``,
                            ``StepMetric``
- ``boundary``           — ``GenerativeBoundary`` (runtime safety guard)
- ``context_assembler``  — ``ContextAssembler``
- ``planner``            — ``WorkflowPlanner``
- ``router``             — ``AgentRouter``
- ``coordinator``        — ``ExecutionCoordinator``

Public API is re-exported lazily from the submodules as they are added
so callers can do::

    from core.orchestrator import SwarmExecutionContext, OrchestrationTrace
"""

from __future__ import annotations

__all__: list[str] = []
