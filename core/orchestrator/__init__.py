"""Anukriti Swarm — Orchestration framework primitives.

This package contains the **reusable orchestration framework** that the
Gemini-powered ``GeminiOrchestrator`` (in ``agents.orchestrator``) is built
on top of. The split follows the project's deterministic/generative
boundary:

- ``core.orchestrator`` — deterministic framework (context, trace, routing,
  coordination, safety boundary). No LLM calls happen here directly except
  inside ``WorkflowPlanner`` and ``ExecutionCoordinator``, and every such
  call is guarded by ``GenerativeBoundary``.
- ``agents.orchestrator.gemini_orchestrator`` — high-level orchestrator that
  uses an ``AIClient`` for *planning and synthesis only*, delegating all
  biomedical reasoning to deterministic agents via this framework.

Public API::

    from core.orchestrator import (
        # state / model
        SwarmExecutionContext, OrchestrationPhase, VerificationState,
        # observability
        OrchestrationTrace, ActivationLog, StepMetric,
        # safety
        GenerativeBoundary, GenerativeAction, GenerativeBoundaryViolation,
        DEFAULT_BOUNDARY,
        # pipeline pieces
        ContextAssembler, WorkflowPlanner, AgentRouter, ExecutionCoordinator,
        PlannedStep, WorkflowPlan, RouteDecision, RoutingResult,
        CoordinationResult,
    )
"""

from __future__ import annotations

from core.orchestrator.boundary import (
    DEFAULT_BOUNDARY,
    GenerativeAction,
    GenerativeBoundary,
    GenerativeBoundaryViolation,
)
from core.orchestrator.context import (
    OrchestrationPhase,
    SwarmExecutionContext,
    VerificationState,
)
from core.orchestrator.context_assembler import ContextAssembler
from core.orchestrator.coordinator import CoordinationResult, ExecutionCoordinator
from core.orchestrator.planner import PlannedStep, WorkflowPlan, WorkflowPlanner
from core.orchestrator.router import AgentRouter, RouteDecision, RoutingResult
from core.orchestrator.trace import (
    ActivationLog,
    OrchestrationTrace,
    StepMetric,
)

__all__ = [
    # state / model
    "SwarmExecutionContext",
    "OrchestrationPhase",
    "VerificationState",
    # observability
    "OrchestrationTrace",
    "ActivationLog",
    "StepMetric",
    # safety
    "GenerativeBoundary",
    "GenerativeAction",
    "GenerativeBoundaryViolation",
    "DEFAULT_BOUNDARY",
    # pipeline pieces
    "ContextAssembler",
    "WorkflowPlanner",
    "AgentRouter",
    "ExecutionCoordinator",
    "PlannedStep",
    "WorkflowPlan",
    "RouteDecision",
    "RoutingResult",
    "CoordinationResult",
]
