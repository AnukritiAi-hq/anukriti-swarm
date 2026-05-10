"""Tests for ``core.runtime.events``.

Contract:
* ``RuntimeEventKind`` is a closed 12-value enum. Extending is a
  code change. Wire-compatible string values must stay stable
  because the FastAPI WebSocket sink and the frontend both key
  off them.
* ``RuntimeEvent`` is frozen and JSON-serializable via ``to_dict``.
* ``InMemoryEventStream`` captures events in order, supports
  subscribers (exceptions are swallowed), and honours ``close()``
  as a silent-drop gate.
"""

from __future__ import annotations

import json

import pytest
from core.runtime.events import (
    EventStream,
    InMemoryEventStream,
    RuntimeEvent,
    RuntimeEventKind,
)

# ---------------------------------------------------------------------------
# Closed-enum contract — wire-compat values
# ---------------------------------------------------------------------------


class TestRuntimeEventKindEnum:
    def test_has_exactly_12_kinds(self) -> None:
        assert len(list(RuntimeEventKind)) == 12

    def test_all_kinds_have_stable_string_values(self) -> None:
        # The FastAPI WebSocket sink and the frontend both key off these
        # exact strings. Changing any is a breaking change for live clients.
        expected = {
            "run_started",
            "agent_activated",
            "retrieval_complete",
            "graph_traversal",
            "sufficiency_decision",
            "verification_checkpoint",
            "uncertainty_transition",
            "provenance_persisted",
            "synthesis_emitted",
            "safe_abstention",
            "run_completed",
            "run_failed",
        }
        assert {k.value for k in RuntimeEventKind} == expected

    def test_unknown_kind_rejected(self) -> None:
        with pytest.raises(ValueError):
            RuntimeEventKind("ehr_ingested")  # out of scope; not in enum


# ---------------------------------------------------------------------------
# RuntimeEvent frozen record
# ---------------------------------------------------------------------------


class TestRuntimeEvent:
    def test_event_id_is_assigned_if_not_supplied(self) -> None:
        e = RuntimeEvent(
            kind=RuntimeEventKind.RUN_STARTED,
            correlation_id="corr-1",
        )
        assert isinstance(e.event_id, str)
        assert len(e.event_id) == 16

    def test_event_id_is_unique_across_default_constructions(self) -> None:
        events = [
            RuntimeEvent(kind=RuntimeEventKind.AGENT_ACTIVATED, correlation_id="x")
            for _ in range(32)
        ]
        ids = {e.event_id for e in events}
        assert len(ids) == 32

    def test_is_frozen(self) -> None:
        e = RuntimeEvent(kind=RuntimeEventKind.RUN_STARTED, correlation_id="corr-1")
        with pytest.raises((AttributeError, Exception)):
            # Dataclass frozen=True raises FrozenInstanceError.
            e.correlation_id = "other"  # type: ignore[misc]

    def test_to_dict_is_jsonable(self) -> None:
        e = RuntimeEvent(
            kind=RuntimeEventKind.SUFFICIENCY_DECISION,
            correlation_id="corr-1",
            payload={"decision": "sufficient", "rule": "R12"},
        )
        payload = json.loads(json.dumps(e.to_dict()))
        assert payload["kind"] == "sufficiency_decision"
        assert payload["correlation_id"] == "corr-1"
        assert payload["payload"]["decision"] == "sufficient"
        # Timestamp must be ISO-8601 parseable.
        from datetime import datetime

        datetime.fromisoformat(payload["timestamp"])


# ---------------------------------------------------------------------------
# InMemoryEventStream behaviour
# ---------------------------------------------------------------------------


class TestInMemoryEventStream:
    def test_emit_records_events_in_order(self) -> None:
        stream = InMemoryEventStream()
        e1 = RuntimeEvent(kind=RuntimeEventKind.RUN_STARTED, correlation_id="c")
        e2 = RuntimeEvent(kind=RuntimeEventKind.AGENT_ACTIVATED, correlation_id="c")
        e3 = RuntimeEvent(kind=RuntimeEventKind.RUN_COMPLETED, correlation_id="c")
        stream.emit(e1)
        stream.emit(e2)
        stream.emit(e3)
        assert stream.events == [e1, e2, e3]

    def test_by_kind_filters_correctly(self) -> None:
        stream = InMemoryEventStream()
        stream.emit(RuntimeEvent(kind=RuntimeEventKind.RUN_STARTED, correlation_id="c"))
        stream.emit(
            RuntimeEvent(
                kind=RuntimeEventKind.AGENT_ACTIVATED,
                correlation_id="c",
                payload={"agent": "orchestrator"},
            )
        )
        stream.emit(
            RuntimeEvent(
                kind=RuntimeEventKind.AGENT_ACTIVATED,
                correlation_id="c",
                payload={"agent": "retrieval"},
            )
        )
        activated = stream.by_kind(RuntimeEventKind.AGENT_ACTIVATED)
        assert len(activated) == 2
        assert {e.payload["agent"] for e in activated} == {"orchestrator", "retrieval"}

    def test_close_is_idempotent_and_silently_drops_subsequent_emits(self) -> None:
        stream = InMemoryEventStream()
        stream.emit(RuntimeEvent(kind=RuntimeEventKind.RUN_STARTED, correlation_id="c"))
        stream.close()
        stream.close()  # second close is a no-op
        # Emits after close must be silently dropped, not raise.
        stream.emit(RuntimeEvent(kind=RuntimeEventKind.RUN_COMPLETED, correlation_id="c"))
        assert len(stream.events) == 1

    def test_subscriber_receives_events(self) -> None:
        stream = InMemoryEventStream()
        received: list[RuntimeEvent] = []
        stream.subscribe(received.append)
        e = RuntimeEvent(kind=RuntimeEventKind.RUN_STARTED, correlation_id="c")
        stream.emit(e)
        assert received == [e]

    def test_subscriber_exceptions_are_swallowed(self) -> None:
        """Broken subscribers must never break the runtime."""
        stream = InMemoryEventStream()

        def bad_subscriber(_: RuntimeEvent) -> None:
            raise RuntimeError("subscriber broken")

        stream.subscribe(bad_subscriber)
        # Must not raise — broken subscriber is isolated.
        stream.emit(RuntimeEvent(kind=RuntimeEventKind.RUN_STARTED, correlation_id="c"))
        assert len(stream.events) == 1

    def test_to_list_returns_jsonable_dicts(self) -> None:
        stream = InMemoryEventStream()
        stream.emit(
            RuntimeEvent(
                kind=RuntimeEventKind.SYNTHESIS_EMITTED,
                correlation_id="c",
                payload={"audience": "clinician"},
            )
        )
        data = stream.to_list()
        assert len(data) == 1
        # Must round-trip through JSON.
        json.dumps(data)
        assert data[0]["kind"] == "synthesis_emitted"


# ---------------------------------------------------------------------------
# EventStream ABC
# ---------------------------------------------------------------------------


class TestEventStreamABC:
    def test_cannot_instantiate_abstract_stream_directly(self) -> None:
        with pytest.raises(TypeError):
            EventStream()  # type: ignore[abstract]

    def test_custom_sink_can_be_implemented(self) -> None:
        class _CountingSink(EventStream):
            def __init__(self) -> None:
                self.count = 0

            def emit(self, event: RuntimeEvent) -> None:
                self.count += 1

        sink = _CountingSink()
        sink.emit(RuntimeEvent(kind=RuntimeEventKind.RUN_STARTED, correlation_id="c"))
        sink.emit(RuntimeEvent(kind=RuntimeEventKind.RUN_COMPLETED, correlation_id="c"))
        assert sink.count == 2

    def test_default_close_is_noop(self) -> None:
        class _MiniSink(EventStream):
            def emit(self, event: RuntimeEvent) -> None:
                pass

        sink = _MiniSink()
        # Base-class close must return None without raising.
        assert sink.close() is None
