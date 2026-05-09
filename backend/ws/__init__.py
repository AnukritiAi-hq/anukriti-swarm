"""WebSocket routers for the Anukriti Swarm backend.

Phase 3 of the Unified Orchestration + Visualization brief.

Submodules:

    run.py       WS /ws/run  (commit 10)
                 Client sends a JSON payload with the scope tuple
                 (drug, gene, population, genotype). Server
                 instantiates SwarmRuntime, subscribes a
                 forwarding sink to the event stream, runs the
                 lifecycle, and sends each RuntimeEvent as a JSON
                 message. Terminates with the final
                 UnifiedExecutionReport.

Scope firewall
--------------
One WebSocket = one run. No multi-run sessions, no pubsub/fanout,
no client-to-client messaging. Broken connections are dropped
silently — runs that started complete their lifecycle, but events
past the disconnect are dropped by the sink's close() discipline.
"""

from __future__ import annotations

__all__: list[str] = []
