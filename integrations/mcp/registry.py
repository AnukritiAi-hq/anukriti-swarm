"""``MCPToolRegistry`` — named tool dispatch with observability.

Every MCP-accessible capability (``memory.store``, ``traces.log``,
``evidence.search``, …) is registered here as a callable. Callers then
invoke tools by name through the registry, which:

1. constructs an ``MCPToolCall`` record (with correlation + origin)
2. times the dispatch
3. wraps the return value in an ``MCPToolResult``
4. folds the result into the shared ``MCPObservability`` snapshot
5. optionally writes the call + result pair to a storage backend for
   audit / replay

Separating the registry from the client (next commit) keeps the
registration model simple and testable: services register their own
tools into a registry they own, then the client is composed from one
or more registries.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from integrations.mcp.backends.base import StorageBackend
from integrations.mcp.models import (
    MCPObservability,
    MCPOrigin,
    MCPToolCall,
    MCPToolResult,
)


# A tool handler takes keyword arguments and returns either:
#   - a plain value (wrapped in MCPToolResult.ok)
#   - an MCPToolResult directly (passed through unchanged)
# Raising is fine — the registry converts exceptions to MCPToolResult.fail.
ToolHandler = Callable[..., Any]


@dataclass
class _RegisteredTool:
    """Internal record bound to a tool name."""

    name: str
    handler: ToolHandler
    description: str = ""
    origin: MCPOrigin = MCPOrigin.SYSTEM  # default origin if caller doesn't override


class ToolNotFoundError(KeyError):
    """Raised when ``invoke`` is called with an unknown tool name."""


class MCPToolRegistry:
    """Named-tool dispatch with built-in observability.

    Usage::

        registry = MCPToolRegistry()
        registry.register("memory.store", store_fn, description="persist agent memory")
        result = registry.invoke(
            "memory.store",
            correlation_id="run-abc",
            origin=MCPOrigin.ORCHESTRATOR,
            args={"agent_id": "x", "data": {...}},
        )

    ``invoke`` always returns an ``MCPToolResult`` — success or failure,
    never raises.
    """

    def __init__(
        self,
        *,
        observability: MCPObservability | None = None,
        audit_backend: StorageBackend | None = None,
        audit_collection: str = "tool_calls",
    ) -> None:
        self._tools: dict[str, _RegisteredTool] = {}
        self.observability = observability or MCPObservability()
        # Optional audit trail: when set, every call + result gets
        # persisted to this backend so we can replay tool invocations
        # later (used by the MCPClient's query APIs).
        self._audit_backend = audit_backend
        self._audit_collection = audit_collection

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        handler: ToolHandler,
        *,
        description: str = "",
        origin: MCPOrigin = MCPOrigin.SYSTEM,
        override: bool = False,
    ) -> None:
        """Register a tool. Raises on duplicates unless ``override=True``."""
        if not name:
            raise ValueError("tool name must be non-empty")
        if name in self._tools and not override:
            raise ValueError(
                f"tool {name!r} already registered; pass override=True to replace"
            )
        self._tools[name] = _RegisteredTool(
            name=name, handler=handler, description=description, origin=origin
        )

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[dict[str, str]]:
        """Return a ``[{"name","description"}]`` list, sorted by name."""
        return [
            {"name": t.name, "description": t.description}
            for t in sorted(self._tools.values(), key=lambda x: x.name)
        ]

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def invoke(
        self,
        name: str,
        *,
        args: dict[str, Any] | None = None,
        correlation_id: str = "",
        called_by: str = "",
        origin: MCPOrigin | None = None,
    ) -> MCPToolResult:
        """Invoke a registered tool by name.

        Never raises. Unknown tools return a failure result; exceptions
        raised inside the handler become failure results too. The
        result is always folded into ``self.observability`` so the
        client's ``snapshot()`` stays consistent.
        """
        args = args or {}
        tool = self._tools.get(name)

        call = MCPToolCall(
            tool=name,
            args=args,
            origin=origin or (tool.origin if tool else MCPOrigin.SYSTEM),
            called_by=called_by,
            correlation_id=correlation_id,
        )

        if tool is None:
            result = MCPToolResult.fail(
                name,
                f"tool {name!r} is not registered",
                tool_call_id=call.id,
            )
            self._record(call, result)
            return result

        t0 = time.perf_counter()
        try:
            raw = tool.handler(**args)
            latency_ms = (time.perf_counter() - t0) * 1000
            if isinstance(raw, MCPToolResult):
                # Handler already produced a structured result. Fill in
                # missing fields (latency / link-back id) but respect
                # its success/error/data otherwise.
                raw.tool_call_id = raw.tool_call_id or call.id
                if not raw.latency_ms:
                    raw.latency_ms = latency_ms
                result = raw
            else:
                result = MCPToolResult.ok(
                    name, data=raw, latency_ms=latency_ms, tool_call_id=call.id
                )
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000
            result = MCPToolResult.fail(
                name,
                f"{type(exc).__name__}: {exc}",
                latency_ms=latency_ms,
                tool_call_id=call.id,
            )

        self._record(call, result)
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _record(self, call: MCPToolCall, result: MCPToolResult) -> None:
        """Observability + optional persistence of the call/result pair."""
        self.observability.record(result)
        if self._audit_backend is not None:
            try:
                self._audit_backend.insert(
                    self._audit_collection,
                    {"call": call.to_dict(), "result": result.to_dict()},
                )
            except Exception:
                # Audit failures never break the invocation path. The
                # service that set up the backend is responsible for
                # surfacing backend issues separately.
                pass


__all__ = ["MCPToolRegistry", "ToolHandler", "ToolNotFoundError"]
