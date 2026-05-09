"""``BiomedicalClaimValidator`` — enforces the 4-field claim mapping.

Requirement #5 of the deterministic safety brief: every biomedical
statement must map to

    1. evidence         at least one source id (PMID / CPIC /
                        PharmGKB / PharmVar) cited on the claim
    2. deterministic    a ``rule_id`` identifying the CPIC /
       rule             Hardy-Weinberg / phenotype rule that
                        produced the claim
    3. source reference a ``guideline_source`` or provenance origin
                        (``CPIC``, ``PharmGKB``, ``PubMed``, …)
    4. verification     a state ∈ {pass, fail, warn} resulting
       outcome          from the validator's judgement

The validator consumes whatever the orchestrator's run dicts
produce (pharmacogene results, population results, recommendations,
retrieval citations, generative narratives) and emits exactly one
``VerificationTrace`` per claim so downstream audit code has a
uniform view.

Intentionally *not* an LLM-based validator. The safety brief is
explicit that validation is deterministic; this engine applies a
small set of pure rules to dicts the pipeline already produces.

Inputs
------
``validate_run(run, *, correlation_id="")`` consumes a single run
dict (the shape ``CoordinationResult.runs[i]`` exposes —
``pharmacogene_result``, ``population_result``, ``recommendations``,
``retrieval_results``, ``citations``, optional ``narrative``). It
returns ``list[VerificationTrace]`` — one entry per validated
claim in a stable order (phenotype → recommendation → retrieval
claim → narrative).

Outputs
-------
Every trace carries the 4 required mapping fields:

    trace.claim              → the biomedical statement
    trace.evidence_refs      → source ids (#1 above)
    trace.rule_id            → deterministic rule id (#2 above)
    trace.reason             → source reference + missing-field diag
    trace.state              → pass / fail / warn (#4 above)

The source reference itself (#3) is not a first-class field on
``VerificationTrace`` — it lives in ``reason`` and is also surfaced
on the owning run's provenance record. The validator FAILs the
claim if any of the first three mapping fields is missing, and
WARNs if a low-confidence non-deterministic claim slipped through
without evidence.

Contract
--------
Pure of external state. No MCP calls, no network. The
``EvidenceGroundingEngine`` (commit 5) *does* touch MCP, and runs
after this validator's output to enrich it. Keeping the split
means unit tests can exercise claim mapping without wiring a
client at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.verification.trace import VerificationTrace, make_trace


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


# Rule-id families. Callers can pass custom ones but these cover the
# deterministic claims the pipeline produces today. Each tuple entry
# is a (claim-kind, default-rule-id) pair used by ``_default_rule_id``.
_DEFAULT_RULE_IDS: dict[str, str] = {
    "phenotype": "cpic.activity_score",
    "recommendation": "cpic.recommendation",
    "population": "hardy_weinberg",
    "retrieval": "evidence.retrieval",
    "narrative": "narrative.synthesis",
}


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


@dataclass
class BiomedicalClaimValidator:
    """Deterministic validator enforcing the 4-field claim mapping.

    Stateless — one instance can validate many runs. Construction
    is zero-arg; callers wire it into the ``VerificationAgent``
    in commit 8.

    Configuration knobs:
      require_evidence_for_deterministic:
        When True (default), a deterministic claim (phenotype /
        recommendation) missing evidence_refs is FAILed. When
        False, it's WARNed — useful for development scenarios
        where evidence retrieval ran dry but we don't want to
        hard-fail the whole pipeline.
      confidence_floor:
        Claims with confidence below this float get WARN even
        when all four mapping fields are present. Default 0.7
        matches the legacy agent's threshold.
    """

    require_evidence_for_deterministic: bool = True
    confidence_floor: float = 0.7

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_run(
        self,
        run: dict[str, Any],
        *,
        correlation_id: str = "",
    ) -> list[VerificationTrace]:
        """Return one ``VerificationTrace`` per validated claim in ``run``.

        Claim order (stable — downstream audit reports rely on it):
          1. phenotype (from ``pharmacogene_result``)
          2. recommendations (from ``recommendations`` list)
          3. population prevalence (from ``population_result``)
          4. retrieval claims (from ``retrieval_results``)
          5. narrative (from ``narrative`` when present)
        """
        traces: list[VerificationTrace] = []
        traces.extend(self._validate_phenotype(run, correlation_id))
        traces.extend(self._validate_recommendations(run, correlation_id))
        traces.extend(self._validate_population(run, correlation_id))
        traces.extend(self._validate_retrieval(run, correlation_id))
        traces.extend(self._validate_narrative(run, correlation_id))
        return traces

    # ------------------------------------------------------------------
    # Individual claim kinds
    # ------------------------------------------------------------------

    def _validate_phenotype(
        self, run: dict[str, Any], cid: str
    ) -> list[VerificationTrace]:
        pgx = run.get("pharmacogene_result") or {}
        if not pgx or not pgx.get("phenotype"):
            return []

        gene = pgx.get("gene") or run.get("gene") or ""
        phenotype = pgx.get("phenotype", "")
        diplo = (run.get("allele1", ""), run.get("allele2", ""))
        if all(diplo):
            claim = f"{gene} {diplo[0]}/{diplo[1]} → {phenotype}"
        elif gene:
            claim = f"{gene} → {phenotype}"
        else:
            claim = phenotype

        evidence_refs = _collect_evidence_refs(run)
        rule_id = _default_rule_id(pgx, "phenotype")
        source_ref = _source_reference(pgx)
        confidence = float(pgx.get("confidence") or 1.0)

        state, reason = self._assess(
            evidence_refs=evidence_refs,
            rule_id=rule_id,
            source_ref=source_ref,
            confidence=confidence,
            is_deterministic=(pgx.get("origin", "deterministic") == "deterministic"),
        )

        return [
            make_trace(
                claim=claim,
                validator="BiomedicalClaimValidator",
                state=state,
                confidence=confidence,
                evidence_refs=tuple(evidence_refs),
                reason=reason,
                correlation_id=cid,
                generating_agent=f"pharmacogene_{gene.lower()}" if gene else "pharmacogene",
                rule_id=rule_id,
            )
        ]

    def _validate_recommendations(
        self, run: dict[str, Any], cid: str
    ) -> list[VerificationTrace]:
        recs = run.get("recommendations") or []
        out: list[VerificationTrace] = []
        fallback_refs = _collect_evidence_refs(run)

        for rec in recs:
            text = rec.get("recommendation") or rec.get("action") or ""
            if not text:
                continue

            # A recommendation's own citations take precedence over
            # run-level fallbacks. Real pipeline shape uses ``pmid`` +
            # ``guideline_id`` rather than a citations list — harvest
            # both paths.
            rec_refs = _citations_to_ids(rec.get("citations") or [])
            for key in ("pmid", "guideline_id"):
                sid = rec.get(key)
                if isinstance(sid, str) and sid and sid not in rec_refs:
                    rec_refs.append(sid)
            evidence_refs = rec_refs or fallback_refs
            rule_id = rec.get("rule_id") or _DEFAULT_RULE_IDS["recommendation"]
            source_ref = rec.get("guideline_source") or _source_reference(rec)
            confidence = float(rec.get("confidence") or 1.0)

            state, reason = self._assess(
                evidence_refs=evidence_refs,
                rule_id=rule_id,
                source_ref=source_ref,
                confidence=confidence,
                is_deterministic=True,  # CPIC recs are deterministic
            )

            out.append(
                make_trace(
                    claim=text,
                    validator="BiomedicalClaimValidator",
                    state=state,
                    confidence=confidence,
                    evidence_refs=tuple(evidence_refs),
                    reason=reason,
                    correlation_id=cid,
                    generating_agent="orchestrator",
                    rule_id=rule_id,
                )
            )
        return out

    def _validate_population(
        self, run: dict[str, Any], cid: str
    ) -> list[VerificationTrace]:
        pop = run.get("population_result") or {}
        if not pop or pop.get("frequency") is None:
            return []

        pop_name = pop.get("population") or run.get("population") or ""
        pgx = run.get("pharmacogene_result") or {}
        gene = pgx.get("gene") or run.get("gene") or ""
        freq = pop.get("frequency")
        claim = (
            f"Frequency of {gene or 'phenotype'} in {pop_name} ≈ {freq}"
            if pop_name
            else f"Frequency of {gene or 'phenotype'} ≈ {freq}"
        )

        # Population estimates are advisory — they don't require
        # evidence_refs but they DO require a rule_id (Hardy-Weinberg).
        evidence_refs = _collect_evidence_refs(run)
        rule_id = _DEFAULT_RULE_IDS["population"]
        source_ref = pop.get("source") or "population_frequency_store"
        confidence = float(pop.get("confidence") or 1.0)

        state, reason = self._assess(
            evidence_refs=evidence_refs,
            rule_id=rule_id,
            source_ref=source_ref,
            confidence=confidence,
            is_deterministic=True,
            # Population estimates can stand without citations — the
            # freq store is itself the evidence. Relax the
            # require-evidence rule for this claim kind.
            require_evidence_override=False,
        )

        return [
            make_trace(
                claim=claim,
                validator="BiomedicalClaimValidator",
                state=state,
                confidence=confidence,
                evidence_refs=tuple(evidence_refs),
                reason=reason,
                correlation_id=cid,
                generating_agent=f"population_{pop_name.lower()}" if pop_name else "population",
                rule_id=rule_id,
            )
        ]

    def _validate_retrieval(
        self, run: dict[str, Any], cid: str
    ) -> list[VerificationTrace]:
        rr = run.get("retrieval_results") or []
        out: list[VerificationTrace] = []
        for item in rr:
            if not isinstance(item, dict):
                continue
            sid = item.get("source_id") or ""
            claim_text = (
                item.get("claim")
                or item.get("title")
                or (item.get("passage") or "")[:80]
            )
            if not claim_text:
                continue
            evidence_refs = [sid] if sid else []
            confidence = float(item.get("confidence") or 1.0)
            state, reason = self._assess(
                evidence_refs=evidence_refs,
                rule_id=_DEFAULT_RULE_IDS["retrieval"],
                source_ref=(item.get("metadata") or {}).get("guideline_source")
                or item.get("source") or "",
                confidence=confidence,
                is_deterministic=False,
            )
            out.append(
                make_trace(
                    claim=claim_text,
                    validator="BiomedicalClaimValidator",
                    state=state,
                    confidence=confidence,
                    evidence_refs=tuple(evidence_refs),
                    reason=reason,
                    correlation_id=cid,
                    generating_agent="retrieval",
                    rule_id=_DEFAULT_RULE_IDS["retrieval"],
                )
            )
        return out

    def _validate_narrative(
        self, run: dict[str, Any], cid: str
    ) -> list[VerificationTrace]:
        narr = run.get("narrative") or ""
        if not narr:
            return []
        # Narratives are generative — they must inherit the evidence
        # the deterministic pipeline already grounded. We don't parse
        # the narrative; we attach the run-level evidence refs as the
        # grounding set.
        evidence_refs = _collect_evidence_refs(run)
        rule_id = _DEFAULT_RULE_IDS["narrative"]
        source_ref = "generative_boundary"
        verif = run.get("verification") or {}
        confidence = float(verif.get("confidence") or 0.0)
        state, reason = self._assess(
            evidence_refs=evidence_refs,
            rule_id=rule_id,
            source_ref=source_ref,
            confidence=confidence,
            is_deterministic=False,
        )
        # Truncate the narrative for the audit trail — full text lives
        # in the orchestrator result.
        snippet = narr if len(narr) < 200 else narr[:197] + "..."
        return [
            make_trace(
                claim=snippet,
                validator="BiomedicalClaimValidator",
                state=state,
                confidence=confidence,
                evidence_refs=tuple(evidence_refs),
                reason=reason,
                correlation_id=cid,
                generating_agent="gemini.orchestrator",
                rule_id=rule_id,
            )
        ]

    # ------------------------------------------------------------------
    # Shared assessment — maps the 4 mapping fields to a state
    # ------------------------------------------------------------------

    def _assess(
        self,
        *,
        evidence_refs: list[str],
        rule_id: str,
        source_ref: str,
        confidence: float,
        is_deterministic: bool,
        require_evidence_override: bool | None = None,
    ) -> tuple[str, str]:
        """Apply the 4-field mapping rule; return (state, reason).

        A claim is FAIL if any required field is missing; WARN if
        all fields present but confidence is below floor; else PASS.

        ``require_evidence_override`` lets callers (population
        estimates) short-circuit the evidence requirement without
        changing the global config.
        """
        requires_evidence = (
            require_evidence_override
            if require_evidence_override is not None
            else (is_deterministic and self.require_evidence_for_deterministic)
        )

        missing: list[str] = []
        if requires_evidence and not evidence_refs:
            missing.append("evidence")
        if not rule_id:
            missing.append("rule_id")
        if not source_ref:
            missing.append("source")

        if missing:
            return (
                "fail",
                f"Missing required mapping field(s): {', '.join(missing)}",
            )

        if confidence < self.confidence_floor:
            return (
                "warn",
                (
                    f"All 4 mapping fields present but confidence "
                    f"{confidence:.2f} below floor {self.confidence_floor:.2f}"
                ),
            )

        summary = []
        if evidence_refs:
            summary.append(f"evidence={len(evidence_refs)} source(s)")
        summary.append(f"rule={rule_id}")
        summary.append(f"source={source_ref}")
        summary.append(f"confidence={confidence:.2f}")
        return "pass", "; ".join(summary)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_evidence_refs(run: dict[str, Any]) -> list[str]:
    """Extract every unique source_id referenced anywhere in a run dict."""
    out: list[str] = []
    for cit in run.get("citations") or []:
        sid = cit if isinstance(cit, str) else (cit.get("source_id") if isinstance(cit, dict) else "")
        if sid and sid not in out:
            out.append(sid)
    for rec in run.get("recommendations") or []:
        for cit in rec.get("citations") or []:
            sid = cit if isinstance(cit, str) else (cit.get("source_id") if isinstance(cit, dict) else "")
            if sid and sid not in out:
                out.append(sid)
        # Real pipeline shape: a recommendation carries pmid +
        # guideline_id directly (not a citations list).
        for key in ("pmid", "guideline_id"):
            sid = rec.get(key) if isinstance(rec, dict) else None
            if isinstance(sid, str) and sid and sid not in out:
                out.append(sid)
    for rr in run.get("retrieval_results") or []:
        sid = rr.get("source_id") if isinstance(rr, dict) else ""
        if sid and sid not in out:
            out.append(sid)
    return out


def _citations_to_ids(citations: list[Any]) -> list[str]:
    """Normalize an arbitrary citations list into a list of source_id strings."""
    out: list[str] = []
    for cit in citations:
        if isinstance(cit, str):
            if cit and cit not in out:
                out.append(cit)
        elif isinstance(cit, dict):
            sid = cit.get("source_id") or ""
            if sid and sid not in out:
                out.append(sid)
    return out


def _default_rule_id(record: dict[str, Any], kind: str) -> str:
    return record.get("rule_id") or _DEFAULT_RULE_IDS.get(kind, f"unknown.{kind}")


def _source_reference(record: dict[str, Any]) -> str:
    """Best-effort resolution of a human-readable source reference.

    Looks at (in order):
      - ``guideline_source`` (explicit)
      - ``provenance.guideline_source`` (nested)
      - ``guideline_id`` (e.g. 'CPIC:CYP2C19:clopidogrel:2022' — parse
        the leading prefix)
      - ``source``
      - if a ``pmid`` is present, use literal 'PubMed' as the source
        kind
    """
    if not isinstance(record, dict):
        return ""
    prov = record.get("provenance") or {}
    explicit = (
        record.get("guideline_source")
        or (prov.get("guideline_source") if isinstance(prov, dict) else "")
    )
    if explicit:
        return explicit
    gid = record.get("guideline_id")
    if isinstance(gid, str) and ":" in gid:
        return gid.split(":", 1)[0]  # 'CPIC:CYP2C19:clopidogrel:2022' → 'CPIC'
    if record.get("pmid"):
        return "PubMed"
    return record.get("source") or ""


__all__ = ["BiomedicalClaimValidator"]
