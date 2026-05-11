"""``ContextAssembler`` — build a ``SwarmExecutionContext`` from raw input.

The orchestrator accepts a variety of input shapes:

- a bare natural-language query string
- structured keyword arguments (gene, drug, population, genotype, …)
- a pre-built ``SwarmExecutionContext`` (for resume / replay)
- the comparative variants (``populations=[…]``, ``drugs=[…]``)

``ContextAssembler`` normalizes all of that into a single, well-typed
``SwarmExecutionContext`` with:

- a stable ``correlation_id``
- a non-empty ``query`` string (synthesized from structured fields if
  the caller didn't provide one)
- a fresh ``OrchestrationTrace`` bound to the same ``correlation_id``
- a starting ``OrchestrationPhase.RECEIVED``

It does **no** reasoning, no LLM calls, and no agent activation — that
belongs to the planner / router / coordinator. The assembler is pure
data shaping so the rest of the pipeline can assume the context is
well-formed.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from core.orchestrator.context import (
    OrchestrationPhase,
    SwarmExecutionContext,
)

if TYPE_CHECKING:
    from core.orchestrator.trace import OrchestrationTrace

# Known populations and genes, used for light query parsing when only a
# freeform string is supplied. Kept intentionally small — the router
# does the real matching via the AgentRegistry.
_KNOWN_POPULATIONS = ("SAS", "AFR", "EUR", "EAS", "AMR")
_KNOWN_GENES = ("CYP2D6", "CYP2C19", "CYP2C9", "HLA-B", "TPMT", "DPYD", "SLCO1B1")
_DIPLOTYPE_RE = re.compile(r"(\*\d+)\s*/\s*(\*\d+)")


class ContextAssembler:
    """Pure assembler — raw inputs -> ``SwarmExecutionContext``.

    Stateless. Safe to share a single instance across orchestrator
    invocations.
    """

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def from_kwargs(
        self,
        *,
        query: str = "",
        gene: str = "",
        drug: str = "",
        population: str = "",
        genotype: dict[str, str] | None = None,
        allele1: str | None = None,
        allele2: str | None = None,
        populations: list[str] | None = None,
        drugs: list[str] | None = None,
    ) -> SwarmExecutionContext:
        """Assemble a context from structured keyword arguments.

        This is the primary path used by the ``GeminiOrchestrator.run``
        method and by the demos.
        """
        geno = dict(genotype or {})
        if gene and (allele1 or allele2):
            geno.setdefault(gene, f"{allele1 or '*1'}/{allele2 or '*1'}")

        ctx = SwarmExecutionContext(
            query=query,
            gene=gene,
            drug=drug,
            population=population,
            genotype=geno,
            populations=list(populations or []),
            drugs=list(drugs or []),
        )
        self._finalize(ctx)
        return ctx

    def from_query(self, query: str, **hints: Any) -> SwarmExecutionContext:
        """Parse a freeform query string, honouring any explicit hints.

        Structured kwargs (gene=…, drug=…, …) always win over parsed
        values; the parser only fills gaps.
        """
        parsed = self._parse_query(query)
        # hints override parsed fields
        for key, value in hints.items():
            if value:
                parsed[key] = value
        parsed.setdefault("query", query)
        return self.from_kwargs(**parsed)

    def resume(self, ctx: SwarmExecutionContext) -> SwarmExecutionContext:
        """Prepare an existing context for (re)execution.

        Used for replay or for restarting after an escalation. Keeps
        history (trace, errors, verification_report) intact but resets
        ``phase`` to RECEIVED so the orchestrator will re-enter the
        planning loop.
        """
        self._finalize(ctx)
        ctx.mark_phase(OrchestrationPhase.RECEIVED)
        return ctx

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _finalize(self, ctx: SwarmExecutionContext) -> None:
        """Fill in derived defaults (query string, trace)."""
        if not ctx.query:
            ctx.query = self._synthesize_query(ctx)
        # ``ensure_trace`` is idempotent; safe on fresh and resumed contexts.
        trace: OrchestrationTrace = ctx.ensure_trace()
        # Keep the trace's query in sync when the caller populated structured
        # fields after constructing the context manually.
        if not trace.query:
            trace.query = ctx.query

    def _synthesize_query(self, ctx: SwarmExecutionContext) -> str:
        """Build a query string from structured fields when none was given."""
        parts: list[str] = []
        if ctx.gene:
            diplo = ctx.genotype.get(ctx.gene, "")
            parts.append(f"{ctx.gene} {diplo}".strip())
        if ctx.drugs:
            parts.append(f"+ {'/'.join(ctx.drugs)}")
        elif ctx.drug:
            parts.append(f"+ {ctx.drug}")
        if ctx.populations:
            parts.append(f"across {', '.join(ctx.populations)}")
        elif ctx.population:
            parts.append(f"in {ctx.population}")
        return " ".join(p for p in parts if p).strip() or "(unstructured query)"

    def _parse_query(self, query: str) -> dict[str, Any]:
        """Best-effort extraction of structured fields from a freeform query.

        This is intentionally lightweight — the LLM planner handles the
        hard cases. The assembler only does high-signal pattern matching
        so the downstream ``AgentRouter`` has something to work with even
        if the LLM is unavailable.
        """
        out: dict[str, Any] = {"query": query}
        upper = query.upper()

        for g in _KNOWN_GENES:
            if g in upper:
                out["gene"] = g
                break

        populations_found = [p for p in _KNOWN_POPULATIONS if p in upper]
        if len(populations_found) == 1:
            out["population"] = populations_found[0]
        elif len(populations_found) > 1:
            out["populations"] = populations_found

        m = _DIPLOTYPE_RE.search(query)
        if m:
            out["allele1"] = m.group(1)
            out["allele2"] = m.group(2)

        return out


# Module-level default, analogous to ``DEFAULT_BOUNDARY``.
DEFAULT_ASSEMBLER = ContextAssembler()


__all__ = ["ContextAssembler", "DEFAULT_ASSEMBLER"]
