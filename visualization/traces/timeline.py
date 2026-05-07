"""Structured execution timeline.

Renders a Gantt-style timeline showing when each agent was active,
with markers for key events (delegation, evidence, verification).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TimelineEvent:
    """A single event on the execution timeline."""

    agent: str
    stage: str
    start_pct: float    # 0.0 - 1.0 position on timeline
    duration_pct: float  # fraction of total time
    status: str
    detail: str = ""


class ExecutionTimeline:
    """Builds and renders a structured execution timeline."""

    def __init__(self, total_ms: float) -> None:
        self.total_ms = total_ms
        self.events: list[TimelineEvent] = []
        self._offset_ms = 0.0

    def add_stage(self, agent: str, stage: str, duration_ms: float, status: str = "success", detail: str = "") -> None:
        """Add a stage to the timeline."""
        start_pct = self._offset_ms / self.total_ms if self.total_ms > 0 else 0
        dur_pct = duration_ms / self.total_ms if self.total_ms > 0 else 0
        self.events.append(TimelineEvent(
            agent=agent, stage=stage,
            start_pct=start_pct, duration_pct=dur_pct,
            status=status, detail=detail,
        ))
        self._offset_ms += duration_ms

    def render(self, width: int = 50) -> str:
        """Render the timeline as ASCII art."""
        lines = [
            "  ┌─ Execution Timeline " + "─" * (width - 20) + "┐",
            f"  │ {'Agent':<20} {'Timeline':<{width}} │",
            "  ├" + "─" * (width + 22) + "┤",
        ]

        status_chars = {"success": "█", "warning": "▓", "error": "░", "pending": "·"}

        for ev in self.events:
            start = int(ev.start_pct * width)
            dur = max(1, int(ev.duration_pct * width))
            char = status_chars.get(ev.status, "█")

            bar = "·" * start + char * dur + "·" * (width - start - dur)
            lines.append(f"  │ {ev.agent:<20} {bar} │")

        lines.append("  ├" + "─" * (width + 22) + "┤")
        lines.append(f"  │ {'0ms':<20} {'':·<{width // 2}}{self.total_ms:.0f}ms{'':·>{width // 2 - len(f'{self.total_ms:.0f}ms')}} │")
        lines.append("  └" + "─" * (width + 22) + "┘")

        return "\n".join(lines)


def build_timeline_from_trace(stages: list[dict[str, Any]], total_ms: float) -> ExecutionTimeline:
    """Build a timeline from pipeline trace stages."""
    timeline = ExecutionTimeline(total_ms)
    for s in stages:
        timeline.add_stage(
            agent=s.get("stage", "unknown"),
            stage=s.get("stage", "unknown"),
            duration_ms=s.get("duration_ms", 0),
            status=s.get("status", "success"),
        )
    return timeline
