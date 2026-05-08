"""``MCPClient`` — top-level facade for the MCP infrastructure.

Single entry point that composes a ``StorageBackend``, a shared
``MCPToolRegistry``, and an ``MCPObservability`` snapshot. Services
(execution memory, trace store, provenance, evidence cache, context
manager) will attach themselves to a single client so they share:

- one persistence backend (avoids each service opening its own Mongo
  connection)
- one observability bucket (so ``client.snapshot()`` summarizes every
  MCP operation the swarm performed)
- one audit collection (every ``invoke`` call/result pair is persisted
  through the same audit seam)

This commit only wires those three together. The individual service
classes (``MCPExecutionMemory`` etc.) land in follow-up commits and
attach their tools to ``client.registry``.
"""

from __future__ import annotations

from typing import Any

from integrations.mcp.backends import StorageBackend, load_default_backend
from integrations.mcp.models import MCPObservability, MCPOrigin, MCPToolResult
from integrations.mcp.registry import MCPToolRegistry


class MCPClient:
    """Composed MCP entry point.

    Parameters
    ----------
    backend:
        Optional ``StorageBackend``. When omitted, the default loader
        picks MongoDB if ``MONGODB_URI`` is set, else ``InMemoryBackend``.
    audit_tool_calls:
        If True (default), every ``invoke`` is persisted via the
        registry's audit hook into the ``tool_calls`` collection of
        the backend.
    """

    def __init__(
        self,
        *,
        backend: StorageBackend | None = None,
        audit_tool_calls: bool = True,
    ) -> None:
        self.backend: StorageBackend = backend or load_default_backend()
        self.observability = MCPObservability()
        self.registry = MCPToolRegistry(
            observability=self.observability,
            audit_backend=self.backend if audit_tool_calls else None,
        )

    # ------------------------------------------------------------------
    # Passthroughs
    # ------------------------------------------------------------------

    @property
    def mode(self) -> str:
        """Backend mode (``in_memory`` or ``mongodb_atlas``)."""
        return self.backend.mode

    def ping(self) -> bool:
        """Health check — ``True`` when the backend is reachable."""
        return self.backend.ping()

    def invoke(
        self,
        tool: str,
        *,
        args: dict[str, Any] | None = None,
        correlation_id: str = "",
        called_by: str = "",
        origin: MCPOrigin | None = None,
    ) -> MCPToolResult:
        """Dispatch a tool call through the registry."""
        return self.registry.invoke(
            tool,
            args=args,
            correlation_id=correlation_id,
            called_by=called_by,
            origin=origin,
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_tools(self) -> list[dict[str, str]]:
        """All registered tools, sorted."""
        return self.registry.list_tools()

    def snapshot(self) -> dict[str, Any]:
        """Rolling observability snapshot for dashboards / logs."""
        snap = self.observability.snapshot()
        snap["backend_mode"] = self.mode
        snap["registered_tools"] = [t["name"] for t in self.list_tools()]
        return snap

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release backend resources if the backend supports it."""
        close = getattr(self.backend, "close", None)
        if callable(close):
            close()


__all__ = ["MCPClient"]
