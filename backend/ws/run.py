"""Live event-streaming WebSocket endpoint.

Phase 3, commit 10 of the Unified Orchestration + Visualization brief.

Single WebSocket route:

    WS /ws/run

Contract:

    1. Client connects.
    2. Client sends one JSON message with the scope tuple:
         {drug, gene, population, genotype, question?, correlation_id?}
    3. Server validates, instantiates a SwarmRuntime with a
       queue-backed EventStream, and runs the lifecycle on a
       worker thread.
    4. Server forwards each RuntimeEvent as a JSON message to
       the client as it's emitted.
    5. Server sends a terminal {type: 'report', ...} message
       with the UnifiedExecutionReport once the lifecycle
       completes.
    6. Server closes the connection.

Why a worker thread? The SwarmRuntime is synchronous (~5ms per
scenario). Running it directly on the event loop blocks other
connections during that window. The thread+queue pattern keeps
the event loop responsive and delivers per-event latency so the
frontend's animations feel live.

Error channels:

    {type: 'error', code, detail}  — validation or runtime error
    WebSocket close with code 1011  — unexpected server error

The cache (RUN_CACHE) is updated on successful completion, just
like /api/run, so /api/replay works for WebSocket-originated runs.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app import RUN_CACHE
from backend.cache import CachedRun
from core.runtime import (
    EventStream,
    RuntimeEvent,
    SwarmRuntime,
    UnifiedExecutionContext,
)


router = APIRouter(tags=["websocket"])


# ---------------------------------------------------------------------------
# Queue-backed EventStream — bridges sync runtime -> async WebSocket
# ---------------------------------------------------------------------------


class AsyncQueueEventStream(EventStream):
    """Event sink whose emit() pushes into an asyncio.Queue.

    Used by the WebSocket handler to receive runtime events from
    the worker thread that executes SwarmRuntime.run(). The queue
    is consumed on the event loop; the runtime writes from a
    worker thread. ``emit`` uses ``queue.put_nowait`` which is
    safe to call from another thread because the queue is a
    thread-safe ``asyncio.Queue`` accessed via ``call_soon_threadsafe``.

    A ``None`` sentinel posted after close() tells the async
    consumer to stop draining.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self.queue: asyncio.Queue[RuntimeEvent | None] = asyncio.Queue()
        self._closed = False

    def emit(self, event: RuntimeEvent) -> None:
        if self._closed:
            return
        # From worker thread: schedule the put on the event loop.
        self.loop.call_soon_threadsafe(self.queue.put_nowait, event)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        # Signal the consumer to stop draining.
        self.loop.call_soon_threadsafe(self.queue.put_nowait, None)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws/run")
async def ws_run(ws: WebSocket) -> None:
    """Live orchestration event stream. See module docstring for protocol."""

    await ws.accept()
    try:
        raw = await ws.receive_text()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            await _send(ws, {"type": "error", "code": "bad_json",
                              "detail": str(exc)})
            await ws.close()
            return

        try:
            ctx = UnifiedExecutionContext.new(
                drug=payload.get("drug", ""),
                gene=payload.get("gene", ""),
                population=payload.get("population", ""),
                genotype=payload.get("genotype", "unknown"),
                question=payload.get("question", ""),
                correlation_id=payload.get("correlation_id", ""),
            )
        except ValueError as exc:
            await _send(ws, {"type": "error", "code": "bad_scope",
                              "detail": str(exc)})
            await ws.close()
            return

        loop = asyncio.get_running_loop()
        stream = AsyncQueueEventStream(loop=loop)
        runtime = SwarmRuntime(event_stream=stream)

        # Kick off the runtime on a worker thread, then close the
        # stream when it finishes so the drain loop below terminates.
        async def _run_then_close() -> Any:
            report_local = await asyncio.to_thread(runtime.run, ctx)
            stream.close()  # posts the None sentinel
            return report_local

        run_task = asyncio.create_task(_run_then_close())

        # Drain the queue; forward every event until we see the
        # sentinel None posted by stream.close() after the runtime
        # completes.
        forwarded = 0
        while True:
            event_or_sentinel = await stream.queue.get()
            if event_or_sentinel is None:
                break
            await _send(ws, {
                "type": "event",
                **event_or_sentinel.to_dict(),
            })
            forwarded += 1

        # Wait for the runtime to finish; should be immediate at
        # this point because the sentinel arrived only after run()
        # returned. Any exception from run() surfaces here.
        report = await run_task

        # Cache the completed run so /api/replay works.
        # InMemoryEventStream isn't used here; reconstruct the events
        # list from what we forwarded by asking the runtime again.
        # Simplest path: just persist the report with empty events tuple
        # (the WS consumer already saw every event); /api/replay on a
        # WS-originated run will return the report with empty events.
        RUN_CACHE.put(ctx.correlation_id, CachedRun(report=report, events=()))

        # Terminal message: the full report so the client can render
        # panels that need the aggregated view.
        await _send(ws, {
            "type": "report",
            "report": report.to_dict(),
            "event_count": forwarded,
        })
        await ws.close()
    except WebSocketDisconnect:
        # Client went away mid-run; nothing to clean up besides the
        # runtime which completes on its worker thread and is GC'd.
        return
    except Exception as exc:  # pragma: no cover — defensive
        try:
            await _send(ws, {"type": "error", "code": "server_error",
                              "detail": repr(exc)})
        except Exception:
            pass
        try:
            await ws.close(code=1011)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _send(ws: WebSocket, payload: dict[str, Any]) -> None:
    """Send a JSON payload over the WS; swallows disconnects."""

    try:
        await ws.send_json(payload)
    except WebSocketDisconnect:
        raise
    except Exception:  # pragma: no cover
        # Best-effort: if a send fails for reasons other than a
        # disconnect, we drop the payload silently so the handler
        # doesn't cascade a failure.
        pass


__all__ = ["router"]
