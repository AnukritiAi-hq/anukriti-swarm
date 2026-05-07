"""CLI trace rendering with colors and status indicators.

Renders execution traces as rich terminal output showing:
- Agent activity with colored status indicators
- Delegation arrows between agents
- Evidence flow with citation markers
- Confidence propagation visualization
- Timing metrics per stage

Designed to make the swarm feel like a living, collaborating system.
"""

from __future__ import annotations

from typing import Any


# ANSI color codes
class _C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    WHITE = "\033[37m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_RED = "\033[41m"


# Status indicators
_STATUS = {
    "success": f"{_C.GREEN}●{_C.RESET}",
    "running": f"{_C.CYAN}◉{_C.RESET}",
    "warning": f"{_C.YELLOW}▲{_C.RESET}",
    "error": f"{_C.RED}✗{_C.RESET}",
    "pending": f"{_C.DIM}○{_C.RESET}",
}

_AGENT_COLORS = {
    "orchestrator": _C.MAGENTA,
    "population": _C.CYAN,
    "pharmacogene": _C.GREEN,
    "retrieval": _C.BLUE,
    "verification": _C.YELLOW,
    "narrative": _C.WHITE,
}


def render_header(correlation_id: str, gene: str, drug: str, population: str) -> str:
    """Render the execution header."""
    lines = [
        "",
        f"  {_C.BOLD}{'═' * 66}{_C.RESET}",
        f"  {_C.BOLD}  🧬 ANUKRITI SWARM — Distributed Genomic Intelligence{_C.RESET}",
        f"  {_C.BOLD}{'═' * 66}{_C.RESET}",
        f"  {_C.DIM}Correlation: {correlation_id}{_C.RESET}",
        f"  {_C.DIM}Query: {gene} / {drug} / {population}{_C.RESET}",
        "",
    ]
    return "\n".join(lines)


def render_stage_start(stage: str, agent: str) -> str:
    """Render a stage starting."""
    color = _AGENT_COLORS.get(stage, _C.WHITE)
    return f"  {_STATUS['running']} {color}{_C.BOLD}{agent:<25}{_C.RESET} {_C.DIM}executing...{_C.RESET}"


def render_stage_complete(stage: str, agent: str, duration_ms: float, status: str = "success", detail: str = "") -> str:
    """Render a completed stage."""
    color = _AGENT_COLORS.get(stage, _C.WHITE)
    indicator = _STATUS.get(status, _STATUS["success"])
    dur = f"{_C.DIM}{duration_ms:>6.1f}ms{_C.RESET}"
    det = f"  {_C.DIM}→ {detail}{_C.RESET}" if detail else ""
    return f"  {indicator} {color}{agent:<25}{_C.RESET} {dur}{det}"


def render_delegation(source: str, target: str, action: str) -> str:
    """Render an agent delegation arrow."""
    return f"  {_C.DIM}    └─▶ {target}: {action}{_C.RESET}"


def render_evidence(citation: str, relevance: float) -> str:
    """Render an evidence retrieval."""
    bar = "█" * int(relevance * 10)
    return f"  {_C.DIM}    📄 [{relevance:.2f}] {citation} {bar}{_C.RESET}"


def render_verification_check(name: str, verdict: str, reason: str) -> str:
    """Render a verification check result."""
    icons = {"pass": f"{_C.GREEN}✓{_C.RESET}", "fail": f"{_C.RED}✗{_C.RESET}", "warn": f"{_C.YELLOW}⚠{_C.RESET}"}
    icon = icons.get(verdict, "?")
    return f"  {_C.DIM}    {icon} {name}: {reason}{_C.RESET}"


def render_confidence_bar(label: str, value: float) -> str:
    """Render a confidence bar."""
    filled = int(value * 20)
    bar = f"{'█' * filled}{'░' * (20 - filled)}"
    if value >= 0.85:
        color = _C.GREEN
    elif value >= 0.60:
        color = _C.YELLOW
    else:
        color = _C.RED
    return f"  {_C.DIM}    {label}: {color}{bar}{_C.RESET} {value:.3f}"


def render_escalation(tier: str, action: str) -> str:
    """Render escalation decision."""
    colors = {"autonomous": _C.GREEN, "multi_agent_review": _C.YELLOW, "human_escalation": _C.RED}
    color = colors.get(tier, _C.WHITE)
    icons = {"autonomous": "✓", "multi_agent_review": "⚠", "human_escalation": "🚨"}
    icon = icons.get(tier, "?")
    return f"  {_C.BOLD}  {icon} Escalation: {color}{tier}{_C.RESET}\n  {_C.DIM}    Action: {action}{_C.RESET}"


def render_footer(total_ms: float, stages: int, verdict: str) -> str:
    """Render the execution footer."""
    color = _C.GREEN if verdict == "pass" else _C.YELLOW if verdict == "warn" else _C.RED
    lines = [
        "",
        f"  {_C.BOLD}{'─' * 66}{_C.RESET}",
        f"  {color}{_C.BOLD}  Pipeline: {verdict.upper()}{_C.RESET} | {stages} stages | {total_ms:.1f}ms total",
        f"  {_C.BOLD}{'═' * 66}{_C.RESET}",
        "",
    ]
    return "\n".join(lines)
