"""``CinematicPlayer`` — paced, narrated event streaming for presentations.

Closes requirement #9 of the observability brief (cinematic demo
mode that visually demonstrates swarm activation, reasoning flow,
verification pipeline, evidence grounding, and final synthesis).

What it is
----------
A thin wrapper around an event stream (live ``ExecutionTracer``
events or replayed ones from ``TraceReplayer.step_through``) that
renders each event with:

    - per-kind icon + color
    - pacing delay (configurable per kind — verification events are
      'slow' by default so judges can read them; MCP events are 'fast')
    - phase-transition narration (when the event kind changes, the
      player emits a banner: "-- VERIFICATION PHASE BEGINS --")
    - optional custom narrator hook for bespoke commentary

What it isn't
-------------
Not a TUI, not a curses app. Pure print-to-stdout with ANSI
colors + time.sleep pacing. That's sufficient for hackathon demo
projection and keeps the demo ``python -m`` runnable anywhere.

Usage
-----

    client = MCPClient()
    # run an orchestration first so there's something to play
    replayer = TraceReplayer(client=client)
    player = CinematicPlayer(
        config=CinematicConfig(base_delay_s=0.4),
        narrator=my_narration_fn,  # optional
    )
    player.play_replay(correlation_id, replayer=replayer)

Or play a live tracer as events are ingested:

    player.attach_live(tracer)  # subscribes to tracer.on_event

Design note: per-event delays are capped at 2s so an over-enthusiastic
config can't stall a live demo indefinitely.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from observability.tracer import EventKind, ExecutionEvent, ExecutionTracer

if TYPE_CHECKING:  # pragma: no cover
    from observability.replay import TraceReplayer


# ANSI codes (matched to the rest of the observability stack)
_B = "\033[1m"
_D = "\033[2m"
_R = "\033[0m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_MAGENTA = "\033[35m"
_CYAN = "\033[36m"
_BLUE = "\033[34m"


# Per-kind display config
_KIND_DISPLAY: dict[EventKind, tuple[str, str, str]] = {
    # (icon, color, human-friendly label)
    EventKind.AGENT_ACTIVATION:   ("▶", _CYAN, "ACTIVATE"),
    EventKind.ROUTING_DECISION:   ("↳", _BLUE, "ROUTE   "),
    EventKind.EVIDENCE_RETRIEVAL: ("📄", _YELLOW, "EVIDENCE"),
    EventKind.VERIFICATION_EVENT: ("✓", _GREEN, "VERIFY  "),
    EventKind.MCP_INTERACTION:    ("⚙", _D, "MCP     "),
    EventKind.GEMINI_STEP:        ("✧", _MAGENTA, "GEMINI  "),
    EventKind.DETERMINISTIC_RULE: ("●", _D, "RULE    "),
}


# Status → status-icon override
_STATUS_ICON: dict[str, str] = {
    "error": f"{_RED}✗{_R}",
    "warning": f"{_YELLOW}⚠{_R}",
}


# Phase narration — a broader grouping than EventKind. Maps each
# event kind onto a "phase" so the player can announce transitions
# (e.g. when we move from deterministic rules into verification
# events, that's the safety phase beginning).
_PHASE: dict[EventKind, str] = {
    EventKind.AGENT_ACTIVATION:   "activation",
    EventKind.ROUTING_DECISION:   "routing",
    EventKind.EVIDENCE_RETRIEVAL: "retrieval",
    EventKind.DETERMINISTIC_RULE: "reasoning",
    EventKind.GEMINI_STEP:        "reasoning",
    EventKind.MCP_INTERACTION:    "persistence",
    EventKind.VERIFICATION_EVENT: "verification",
}

_PHASE_BANNERS: dict[str, str] = {
    "activation":   "🚀 SWARM ACTIVATION",
    "routing":      "🧭 ROUTING + PLANNING",
    "retrieval":    "📚 EVIDENCE RETRIEVAL",
    "reasoning":    "🧠 DETERMINISTIC + GENERATIVE REASONING",
    "persistence":  "💾 MCP PERSISTENCE",
    "verification": "🛡  VERIFICATION + SAFETY",
}


NarratorHook = Callable[[ExecutionEvent], str]
"""Callback signature: given an event, return narration text or empty."""


# ---------------------------------------------------------------------------
# Config + player
# ---------------------------------------------------------------------------


@dataclass
class CinematicConfig:
    """Tunables for the cinematic player."""

    base_delay_s: float = 0.3         # baseline pacing between events
    kind_multipliers: dict[EventKind, float] = field(
        default_factory=lambda: {
            EventKind.AGENT_ACTIVATION:   1.5,
            EventKind.ROUTING_DECISION:   1.2,
            EventKind.EVIDENCE_RETRIEVAL: 1.3,
            EventKind.VERIFICATION_EVENT: 2.0,  # slowest — judges read these
            EventKind.MCP_INTERACTION:    0.3,  # fastest
            EventKind.GEMINI_STEP:        1.8,
            EventKind.DETERMINISTIC_RULE: 0.8,
        }
    )
    max_delay_s: float = 2.0          # cap so a bad config can't stall
    show_phase_banners: bool = True   # announce phase transitions
    show_status_icon: bool = True
    silent: bool = False              # turn off all output (for tests)

    def delay_for(self, kind: EventKind) -> float:
        raw = self.base_delay_s * self.kind_multipliers.get(kind, 1.0)
        return max(0.0, min(raw, self.max_delay_s))


@dataclass
class CinematicPlayer:
    """Presentation-mode event player.

    Stateful between plays: tracks the last phase so banners only
    fire on transitions. ``reset()`` clears the phase memory.
    """

    config: CinematicConfig = field(default_factory=CinematicConfig)
    narrator: NarratorHook | None = None
    _last_phase: str = ""
    _events_played: int = 0
    _out = sys.stdout

    # ------------------------------------------------------------------
    # Live attachment
    # ------------------------------------------------------------------

    def attach_live(self, tracer: ExecutionTracer) -> None:
        """Subscribe to a tracer — every ingested event animates live.

        Bypasses pacing (live events already arrive one-at-a-time
        from the orchestrator); renders each one as it arrives.
        """
        tracer.on_event(lambda ev: self._render(ev, pace=False))

    # ------------------------------------------------------------------
    # Replay playback
    # ------------------------------------------------------------------

    def play_replay(
        self,
        correlation_id: str,
        *,
        replayer: "TraceReplayer",
    ) -> int:
        """Play a replayed run frame-by-frame with pacing.

        Returns the count of events rendered.
        """
        if not self.config.silent:
            self._banner(
                f"▶ PLAYING REPLAY — correlation_id={correlation_id}"
            )
        count = 0
        for ev in replayer.step_through(correlation_id, delay_s=0.0):
            # We drive pacing ourselves (step_through delay_s=0) so
            # the player can give different pacing per kind.
            self._render(ev, pace=True)
            count += 1
        if not self.config.silent:
            self._banner(f"■ REPLAY COMPLETE — {count} event(s)")
        return count

    def play_events(self, events: list[ExecutionEvent]) -> int:
        """Play an explicit event list (useful for tests + synthetic runs)."""
        count = 0
        for ev in events:
            self._render(ev, pace=True)
            count += 1
        return count

    def reset(self) -> None:
        self._last_phase = ""
        self._events_played = 0

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self, ev: ExecutionEvent, *, pace: bool) -> None:
        # Always count the event — silent mode only suppresses output,
        # not the bookkeeping the player does for tests / debugging.
        self._events_played += 1
        if self.config.silent:
            # Silent mode still pays out pacing so timing-sensitive
            # tests can use it to exercise the delay path, but
            # defaults to base_delay_s=0 in tests so this is free.
            if pace:
                time.sleep(self.config.delay_for(ev.kind))
            return

        # Phase-transition banner.
        phase = _PHASE.get(ev.kind, "")
        if (
            phase
            and phase != self._last_phase
            and self.config.show_phase_banners
        ):
            self._banner(_PHASE_BANNERS.get(phase, phase.upper()))
            self._last_phase = phase

        icon, color, label = _KIND_DISPLAY.get(
            ev.kind, ("•", _D, ev.kind.value.upper())
        )
        if self.config.show_status_icon and ev.status in _STATUS_ICON:
            icon = _STATUS_ICON[ev.status]

        name = ev.name
        if len(name) > 38:
            name = name[:35] + "..."

        line = (
            f"  {color}{icon}{_R}  {_B}{label}{_R}  "
            f"{color}{name:<40}{_R}  "
            f"{_D}{ev.duration_ms:>6.2f}ms{_R}"
        )
        print(line, file=self._out)

        # Narrator hook.
        if self.narrator is not None:
            try:
                commentary = self.narrator(ev)
            except Exception:
                commentary = ""
            if commentary:
                print(f"        {_D}{commentary}{_R}", file=self._out)

        # Pay out the pacing delay.
        if pace:
            time.sleep(self.config.delay_for(ev.kind))

    def _banner(self, title: str) -> None:
        bar = "─" * 66
        print(f"\n  {_B}{bar}{_R}", file=self._out)
        print(f"  {_B}{_CYAN}  {title}{_R}", file=self._out)
        print(f"  {_B}{bar}{_R}\n", file=self._out)


__all__ = [
    "CinematicPlayer",
    "CinematicConfig",
    "NarratorHook",
]
