"""``MCPMemoryAdvisor`` — memory-aware orchestration pre-consultation.

The hook layer in ``integrations.mcp.persistence_hook`` handles the
*write* side of memory-aware orchestration: everything an
orchestration run produces lands in MCP. This module handles the
*read* side: before a new run is planned, the orchestrator asks the
advisor "have we seen this (gene, drug, population) before?" and
receives a compact summary of prior runs.

Placement
---------
Kept in ``integrations.mcp`` (next to ``MCPRetrieval``) rather than
in ``core.orchestrator`` because:

  1. it's a *client* of MCP services — not orchestration primitives
  2. it must be swappable at construction time (tests use a stub, prod
     wires the real advisor), which fits the ``integrations`` surface
  3. ``core.orchestrator`` stays free of MCP import dependencies —
     orchestration runs fine without MCP (the demo's in-memory mode
     proves that)

Contract
--------

    advisor = MCPMemoryAdvisor(client)
    prior = advisor.consult(gene="CYP2C19", drug="clopidogrel", population="SAS")
    prior.runs                    # list[dict] — run summaries, newest first
    prior.has_prior               # bool
    prior.concordance_hint        # str — "aligned" / "mixed" / "first_run"
    prior.to_planning_hint()      # str — compact text for the planner

The orchestrator (``agents/orchestrator/gemini_orchestrator.py``)
accepts an optional ``memory_advisor`` on construction; when present
it's consulted once per ``run()`` before planning. The advisor is
purely additive: orchestrators constructed without one behave
identically to before.

Why a dedicated advisor vs direct use of ``MCPRetrieval.lookup_prior``?
--------------------------------------------------------------------
Three reasons:

  1. **Framing.** The advisor packages prior runs into a
     ``PriorRunDigest`` that's specifically shaped for planning
     (e.g. ``concordance_hint`` summarizes whether past verdicts
     agreed — the planner doesn't need raw run dicts).
  2. **Observability.** Each consultation records a single trace
     step (``memory.consult``), so the read-side appears in the
     same observability lens as the write-side.
  3. **Policy.** Caps result volume, drops stale runs, and masks
     any runs where verification failed — policy that shouldn't
     leak into the orchestrator.

Non-goals
---------
- **No** re-execution. The advisor never calls the orchestrator.
- **No** mutation of the returned run dicts. Callers get an
  immutable read-only view.
- **No** network or Mongo-specific calls — runs on top of
  ``MCPRetrieval``, so it works against the in-memory backend too.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from integrations.mcp.client import MCPClient
from integrations.mcp.retrieval import MCPRetrieval


# ---------------------------------------------------------------------------
# Digest — what the advisor hands back
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PriorRunDigest:
    """Compact summary of prior runs for one (gene, drug, population) tuple.

    Frozen so downstream code can't accidentally mutate historical
    results. ``runs`` is a defensive-copied list of dicts the memory
    service returned.
    """

    gene: str
    drug: str
    population: str
    runs: list[dict[str, Any]] = field(default_factory=list)
    concordance_hint: str = "first_run"  # first_run | aligned | mixed | degraded

    @property
    def has_prior(self) -> bool:
        """True when at least one past run matched the query axes."""
        return bool(self.runs)

    @property
    def count(self) -> int:
        return len(self.runs)

    def recent_verdicts(self) -> list[str]:
        """Verification states from each prior run, newest first."""
        return [str(r.get("verification_state", "")).lower() for r in self.runs]

    def to_planning_hint(self) -> str:
        """One-line text injectable into planner prompts or trace steps.

        Shape examples::

            "no prior runs for CYP2C19+clopidogrel+SAS"
            "3 prior runs (all passed)"
            "2 prior runs (mixed verdicts: passed, warning)"
        """
        if not self.runs:
            return (
                f"no prior runs for "
                f"{self.gene or '—'}+{self.drug or '—'}+{self.population or '—'}"
            )
        verdicts = self.recent_verdicts()
        unique = sorted(set(verdicts))
        if len(unique) == 1:
            return f"{self.count} prior run(s) (all {unique[0]})"
        return f"{self.count} prior run(s) (mixed verdicts: {', '.join(unique)})"

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict view for logging / trace attachment."""
        return {
            "gene": self.gene,
            "drug": self.drug,
            "population": self.population,
            "count": self.count,
            "concordance_hint": self.concordance_hint,
            "recent_verdicts": self.recent_verdicts(),
            "hint": self.to_planning_hint(),
        }


# ---------------------------------------------------------------------------
# Advisor
# ---------------------------------------------------------------------------


# Verification states we treat as "safe to learn from". Anything else
# (failed, pending) is surfaced in the digest but doesn't contribute
# to the concordance hint — we don't want a bad past run to nudge
# future plans.
_SAFE_VERDICTS = {"passed", "warning"}


@dataclass
class MCPMemoryAdvisor:
    """Read-side of memory-aware orchestration.

    Composes an ``MCPRetrieval`` aggregator and exposes a single
    ergonomic ``consult()`` method the orchestrator can call once per
    run. Stateless between calls.
    """

    client: MCPClient
    max_runs: int = 5

    def __post_init__(self) -> None:
        # ``MCPRetrieval`` re-attaches all services with override=True,
        # so this is safe even if the client already has services
        # registered from another code path.
        self.retrieval = MCPRetrieval(client=self.client)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def consult(
        self,
        *,
        gene: str = "",
        drug: str = "",
        population: str = "",
    ) -> PriorRunDigest:
        """Return a digest of prior runs matching the given axes.

        At least one axis must be supplied (otherwise the result
        would be "all runs ever" — meaningless for planning).
        Empty axes are simply not filtered on, so
        ``consult(gene="CYP2C19")`` returns every CYP2C19 run
        regardless of drug/population.
        """
        if not (gene or drug or population):
            raise ValueError(
                "MCPMemoryAdvisor.consult requires at least one of "
                "gene / drug / population"
            )

        raw = self.retrieval.lookup_prior(
            gene=gene, drug=drug, population=population, limit=self.max_runs
        )

        # Defensive copy — the retrieval layer returns mutable dicts
        # but the digest is frozen.
        runs = [dict(r) for r in raw]

        return PriorRunDigest(
            gene=gene,
            drug=drug,
            population=population,
            runs=runs,
            concordance_hint=self._concordance_hint(runs),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _concordance_hint(runs: list[dict[str, Any]]) -> str:
        """Summarize whether prior verdicts agree.

        - ``first_run``  — no prior runs
        - ``aligned``    — every run ended in the same safe state
        - ``mixed``      — safe verdicts disagree (pass vs warning)
        - ``degraded``   — at least one run failed or is pending
        """
        if not runs:
            return "first_run"
        states = [str(r.get("verification_state", "")).lower() for r in runs]
        if any(s not in _SAFE_VERDICTS for s in states):
            return "degraded"
        if len(set(states)) == 1:
            return "aligned"
        return "mixed"


__all__ = ["MCPMemoryAdvisor", "PriorRunDigest"]
