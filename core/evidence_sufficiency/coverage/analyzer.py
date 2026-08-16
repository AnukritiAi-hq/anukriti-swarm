"""``EvidenceCoverageAnalyzer`` — deterministic per-facet coverage.

Phase 1 of the Evidence Sufficiency Layer brief.

Computes a ``ClaimCoverageAnalysis`` (commit 2) from the dicts the
orchestrator already produces + the retrieval result + (optionally)
an MCP evidence cache handle. Pure function — no LLM, no network
IO during analysis. The five inputs are identical to what
``BiomedicalClaimValidator`` consumes, keeping the surfaces
consistent across the verification stack.

Per-facet rules
---------------
Each of the six closed facets has exactly one deterministic rule
for COVERED / MISSING / UNCERTAIN. The rules are intentionally
conservative: the analyzer errs on the side of UNCERTAIN rather
than silently counting as COVERED. Upstream callers who need a
stricter reading can inspect ``facet_evidence_refs`` directly.

    ALLELE          COVERED iff at least one retrieval document
                    whose ``genes`` includes ``run["gene"]`` and
                    whose source is PharmGKB / PharmVar / PubMed
                    resolves to a citation id. MISSING otherwise.

    PHENOTYPE       COVERED iff ``run["pharmacogene_result"]`` has
                    a non-empty ``phenotype`` backed by a rule_id
                    in the cpic.* family. UNCERTAIN if phenotype
                    is present but the rule_id is missing.
                    MISSING otherwise.

    CPIC            COVERED iff at least one CPIC-sourced document
                    in the retrieval set matches both the gene and
                    the drug. UNCERTAIN if a CPIC document matches
                    the gene but not the drug. MISSING otherwise.

    POPULATION      COVERED iff ``run["population_result"]`` is
                    present **and** a retrieval/citation reference
                    mentions the target population context — allele
                    frequency evidence for that super-population is
                    what's being asserted. UNCERTAIN if the
                    population result exists but no citation
                    supports it. MISSING otherwise.

    RECOMMENDATION  COVERED iff ``run["recommendations"]`` is
                    non-empty and **each** recommendation carries
                    at least one evidence id (PMID / CPIC /
                    PharmGKB). UNCERTAIN if recommendations are
                    present but any is uncited. MISSING otherwise.

    CONFLICT_FREE   Defaulted to COVERED with evidence_refs=() —
                    the ``ConflictDetectionAgent`` in commit 4
                    downgrades it to MISSING/UNCERTAIN if it
                    detects a contradiction. Keeping the default
                    optimistic keeps the analyzer's concern narrow:
                    coverage, not conflict.

Inputs
------
``analyze(run, retrieval_docs=None, correlation_id="")`` —
  run:              a single orchestrator run dict with the shape
                    ``CoordinationResult.runs[i]`` exposes
                    (pharmacogene_result / population_result /
                    recommendations / retrieval_results / citations)
  retrieval_docs:   iterable of ``BiomedicalDocument`` backing the
                    run's retrieval. Used to match gene/drug on the
                    document side deterministically. If omitted the
                    analyzer falls back to inspecting
                    ``run["retrieval_results"]`` metadata — less
                    precise but still deterministic.
  correlation_id:   propagated into the resulting analysis for
                    MCP-side linkage. Matches the analogous argument
                    on ``BiomedicalClaimValidator.validate_run``.

The analyzer is stateless. One instance can analyze many runs in
any order; no shared mutable state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

from core.evidence_sufficiency.coverage.claim_coverage import (
    ALL_FACETS,
    ClaimCoverageAnalysis,
    ClaimEvidenceFacet,
    FacetCoverageState,
)
from core.models.population import SuperPopulation

# The closed anchor table + matcher live in ``core.models.population_mentions``
# so the retrieval subpackage can share the exact same vocabulary without
# reaching into a private analyzer symbol. Aliased here under the legacy
# underscore name so any in-tree import still resolves.
from core.models.population_mentions import (
    mentions_population as _mentions_population,
)

# ---------------------------------------------------------------------------
# Document-shape adapter
# ---------------------------------------------------------------------------


# We accept both ``BiomedicalDocument`` instances and any dict with the
# same minimal shape so the analyzer composes with cached / mocked /
# live retrieval equally well. The minimal shape is documented here
# and checked at call time rather than enforced via a Protocol — the
# existing codebase doesn't use Protocols for retrieval adapters.
_REQUIRED_DOC_KEYS = ("doc_id", "source", "genes", "drugs", "citation_id")


def _as_doc_dict(doc: Any) -> dict[str, Any] | None:
    """Normalize a document-like value to a minimal dict; None if incompatible.

    Required keys (listed in ``_REQUIRED_DOC_KEYS``) gate normalization.
    Additional fields the population-mention rule consumes —
    ``title`` and ``keywords`` — are carried through when present and
    default to empty when the input doesn't expose them. That makes
    the normalizer permissive on input shape without changing the
    required contract.
    """

    if doc is None:
        return None
    # dataclass BiomedicalDocument
    if all(hasattr(doc, k) for k in _REQUIRED_DOC_KEYS):
        return {
            "doc_id": doc.doc_id,
            "source": doc.source,
            "genes": list(doc.genes or []),
            "drugs": list(doc.drugs or []),
            "citation_id": doc.citation_id,
            "title": str(getattr(doc, "title", "") or ""),
            "keywords": list(getattr(doc, "keywords", ()) or ()),
        }
    # plain dict
    if isinstance(doc, dict) and all(k in doc for k in _REQUIRED_DOC_KEYS):
        return {
            "doc_id": doc["doc_id"],
            "source": doc["source"],
            "genes": list(doc.get("genes") or []),
            "drugs": list(doc.get("drugs") or []),
            "citation_id": doc["citation_id"],
            "title": str(doc.get("title", "") or ""),
            "keywords": list(doc.get("keywords", ()) or ()),
        }
    return None


def _source_name(source: Any) -> str:
    """Extract the string name of a source value (enum or str)."""

    val = getattr(source, "value", None)
    if isinstance(val, str):
        return val
    return str(source)


# ---------------------------------------------------------------------------
# Population-mention rules
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


@dataclass
class EvidenceCoverageAnalyzer:
    """Deterministic 6-facet coverage analyzer.

    Stateless and deterministic — same inputs always produce the
    same ``ClaimCoverageAnalysis``. One instance handles many runs.

    Options
    -------
    ``require_recommendation_citations``: when True (default), every
    recommendation must carry at least one citation for the
    RECOMMENDATION facet to be COVERED. When False, presence of at
    least one cited recommendation suffices. Default matches the
    verification stack's ``require_evidence_for_deterministic``
    discipline.
    """

    require_recommendation_citations: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        run: dict[str, Any],
        *,
        retrieval_docs: Iterable[Any] | None = None,
        correlation_id: str = "",
    ) -> ClaimCoverageAnalysis:
        """Produce a ``ClaimCoverageAnalysis`` for ``run``.

        ``run`` must carry at minimum a ``gene``, ``drug``, and
        ``population`` (as ``SuperPopulation`` or its .value string).
        ``genotype`` is optional; callers that omit it get "unknown".
        """

        gene = str(run.get("gene") or "").strip()
        drug = str(run.get("drug") or "").strip()
        genotype = self._format_genotype(run)
        population = self._coerce_population(run.get("population"))

        analysis = ClaimCoverageAnalysis.empty(
            drug=drug,
            gene=gene,
            genotype=genotype,
            population=population,
            correlation_id=correlation_id,
        )

        docs = [
            normalized
            for normalized in (_as_doc_dict(d) for d in (retrieval_docs or ()))
            if normalized is not None
        ]

        # Apply the six facet rules in ALL_FACETS order so the
        # audit log reads consistently.
        for facet in ALL_FACETS:
            state, refs, reason = self._apply_facet_rule(facet, run, docs, gene, drug, population)
            analysis = analysis.with_facet(
                facet,
                state=state,
                evidence_refs=refs,
                reason=reason,
            )
        return analysis

    # ------------------------------------------------------------------
    # Input coercion
    # ------------------------------------------------------------------

    @staticmethod
    def _format_genotype(run: dict[str, Any]) -> str:
        a1 = str(run.get("allele1") or "").strip()
        a2 = str(run.get("allele2") or "").strip()
        if a1 and a2:
            return f"{a1}/{a2}"
        explicit = str(run.get("genotype") or "").strip()
        return explicit or "unknown"

    @staticmethod
    def _coerce_population(raw: Any) -> SuperPopulation:
        """Accept either a SuperPopulation instance or a canonical code string.

        The closed enum is the scope firewall. Strings that don't match
        a known code raise ``ValueError`` — there's no silent fallback.
        """

        if isinstance(raw, SuperPopulation):
            return raw
        if isinstance(raw, str) and raw.strip():
            return SuperPopulation(raw.strip().upper())
        raise ValueError(
            "run['population'] must be a SuperPopulation or a 3-letter "
            "super-population code (AFR / AMR / EAS / EUR / SAS); "
            f"got {raw!r}"
        )

    # ------------------------------------------------------------------
    # Per-facet rules — one private method per facet, all deterministic
    # ------------------------------------------------------------------

    def _apply_facet_rule(
        self,
        facet: ClaimEvidenceFacet,
        run: dict[str, Any],
        docs: list[dict[str, Any]],
        gene: str,
        drug: str,
        population: SuperPopulation,
    ) -> tuple[FacetCoverageState, tuple[str, ...], str]:
        if facet is ClaimEvidenceFacet.ALLELE:
            return self._facet_allele(docs, gene)
        if facet is ClaimEvidenceFacet.PHENOTYPE:
            return self._facet_phenotype(run, gene)
        if facet is ClaimEvidenceFacet.CPIC:
            return self._facet_cpic(docs, gene, drug)
        if facet is ClaimEvidenceFacet.POPULATION:
            return self._facet_population(run, docs, gene, population)
        if facet is ClaimEvidenceFacet.RECOMMENDATION:
            return self._facet_recommendation(run)
        if facet is ClaimEvidenceFacet.CONFLICT_FREE:
            return self._facet_conflict_free_default()
        raise AssertionError(f"unhandled facet {facet!r}")

    @staticmethod
    def _facet_allele(
        docs: list[dict[str, Any]], gene: str
    ) -> tuple[FacetCoverageState, tuple[str, ...], str]:
        allele_source_names = {"PharmGKB", "PubMed", "PharmVar"}
        refs: list[str] = []
        for d in docs:
            if not gene or gene.upper() not in (g.upper() for g in d["genes"]):
                continue
            if _source_name(d["source"]) in allele_source_names:
                refs.append(str(d["citation_id"]))
        if refs:
            return (
                FacetCoverageState.COVERED,
                tuple(dict.fromkeys(refs)),  # dedup, preserve order
                f"{len(refs)} allele-bearing source(s) cite {gene}",
            )
        return (
            FacetCoverageState.MISSING,
            (),
            f"no PharmGKB/PubMed/PharmVar source cites {gene or 'the gene'}",
        )

    @staticmethod
    def _facet_phenotype(
        run: dict[str, Any], gene: str
    ) -> tuple[FacetCoverageState, tuple[str, ...], str]:
        pgx = run.get("pharmacogene_result") or {}
        phenotype = str(pgx.get("phenotype") or "").strip()
        if not phenotype:
            return (
                FacetCoverageState.MISSING,
                (),
                "no phenotype produced by pharmacogene agent",
            )
        rule_id = str(pgx.get("rule_id") or "").strip()
        if rule_id.startswith("cpic.") or rule_id.startswith("hla_b."):
            return (
                FacetCoverageState.COVERED,
                (rule_id,),
                f"{gene or 'phenotype'} backed by rule {rule_id}",
            )
        return (
            FacetCoverageState.UNCERTAIN,
            (),
            "phenotype present but no cpic.* / hla_b.* rule_id attached",
        )

    @staticmethod
    def _facet_cpic(
        docs: list[dict[str, Any]], gene: str, drug: str
    ) -> tuple[FacetCoverageState, tuple[str, ...], str]:
        gene_u = gene.upper()
        drug_l = drug.lower()
        both_match: list[str] = []
        gene_only: list[str] = []
        for d in docs:
            if _source_name(d["source"]) != "CPIC":
                continue
            gene_hit = gene_u and gene_u in (g.upper() for g in d["genes"])
            drug_hit = drug_l and drug_l in (s.lower() for s in d["drugs"])
            if gene_hit and drug_hit:
                both_match.append(str(d["citation_id"]))
            elif gene_hit:
                gene_only.append(str(d["citation_id"]))
        if both_match:
            return (
                FacetCoverageState.COVERED,
                tuple(dict.fromkeys(both_match)),
                f"{len(both_match)} CPIC guideline(s) cover {gene}+{drug}",
            )
        if gene_only:
            return (
                FacetCoverageState.UNCERTAIN,
                tuple(dict.fromkeys(gene_only)),
                f"CPIC evidence for {gene} exists but not paired with {drug or 'drug'}",
            )
        return (
            FacetCoverageState.MISSING,
            (),
            f"no CPIC guideline for {gene or 'gene'} + {drug or 'drug'}",
        )

    @staticmethod
    def _facet_population(
        run: dict[str, Any],
        docs: list[dict[str, Any]],
        gene: str,
        population: SuperPopulation,
    ) -> tuple[FacetCoverageState, tuple[str, ...], str]:
        pop_result = run.get("population_result") or {}
        has_pop_result = bool(pop_result and pop_result.get("frequency") is not None)

        # Population-allele context is a property of a (gene, population)
        # pair, not just population. Filter candidate docs by gene
        # overlap so that, e.g., a DPYD/SAS evidence paper does not
        # satisfy the POPULATION facet for a CYP2D6/SAS run. This
        # mirrors the gene-scoping ``_facet_cpic`` and ``_facet_allele``
        # already enforce.
        gene_u = (gene or "").upper()

        def _doc_in_gene_scope(d: dict[str, Any]) -> bool:
            if not gene_u:
                return True
            return gene_u in (str(g).upper() for g in d.get("genes") or ())

        # Consider docs whose title or keywords mention the population.
        refs: list[str] = []
        for d in docs:
            if not _doc_in_gene_scope(d):
                continue
            hay = " ".join(
                [
                    str(d.get("title", "")),
                    " ".join(str(k) for k in d.get("keywords", [])),
                ]
            ).strip()
            if hay and _mentions_population(hay, population):
                refs.append(str(d["citation_id"]))

        # Also accept retrieval_results metadata if docs weren't passed.
        # Retrieval results carry a ``genes`` field when sourced from
        # the in-tree document store; honour it when present so the
        # gene-scope discipline applies on this fallback path too.
        if not refs:
            for ev in run.get("retrieval_results") or []:
                ev_genes = ev.get("genes") or ev.get("gene_tags") or ()
                if gene_u and ev_genes and gene_u not in (str(g).upper() for g in ev_genes):
                    continue
                text = " ".join(
                    [
                        str(ev.get("title", "")),
                        str(ev.get("content", ""))[:400],
                    ]
                )
                if _mentions_population(text, population):
                    cid = str(ev.get("citation_id") or ev.get("evidence_id") or "")
                    if cid:
                        refs.append(cid)

        if has_pop_result and refs:
            return (
                FacetCoverageState.COVERED,
                tuple(dict.fromkeys(refs)),
                f"{len(refs)} source(s) support {population.value} allele context",
            )
        if has_pop_result and not refs:
            return (
                FacetCoverageState.UNCERTAIN,
                (),
                f"population agent reported a frequency for {population.value} "
                f"but no citation mentions the population",
            )
        return (
            FacetCoverageState.MISSING,
            (),
            f"no {population.value} population evidence",
        )

    def _facet_recommendation(
        self, run: dict[str, Any]
    ) -> tuple[FacetCoverageState, tuple[str, ...], str]:
        recs = list(run.get("recommendations") or [])
        if not recs:
            return (
                FacetCoverageState.MISSING,
                (),
                "no prescribing recommendation produced",
            )

        cited_refs: list[str] = []
        uncited = 0
        for rec in recs:
            rec_refs = list(rec.get("evidence_refs") or rec.get("sources") or [])
            if rec_refs:
                cited_refs.extend(str(r) for r in rec_refs)
            else:
                uncited += 1

        if cited_refs and uncited == 0:
            return (
                FacetCoverageState.COVERED,
                tuple(dict.fromkeys(cited_refs)),
                f"{len(recs)} recommendation(s), all cite evidence",
            )
        if cited_refs and self.require_recommendation_citations:
            return (
                FacetCoverageState.UNCERTAIN,
                tuple(dict.fromkeys(cited_refs)),
                f"{uncited}/{len(recs)} recommendation(s) uncited under strict mode",
            )
        if cited_refs:
            return (
                FacetCoverageState.COVERED,
                tuple(dict.fromkeys(cited_refs)),
                f"{len(cited_refs)} cited recommendation(s); lenient mode",
            )
        return (
            FacetCoverageState.MISSING,
            (),
            "recommendations present but none cite evidence",
        )

    @staticmethod
    def _facet_conflict_free_default() -> tuple[FacetCoverageState, tuple[str, ...], str]:
        # ConflictDetectionAgent (commit 4) downgrades this if it finds
        # a contradiction. Default optimistic so the *coverage* analyzer
        # stays concerned with coverage only.
        return (
            FacetCoverageState.COVERED,
            (),
            "no conflict detected by coverage analyzer (pending conflict pass)",
        )


__all__ = ["EvidenceCoverageAnalyzer"]
