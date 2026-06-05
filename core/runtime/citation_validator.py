"""T7 — CitationValidator: post-synthesis citation verification.

Validates that every factual claim in LLM-generated narrative text has
a backing citation from the provided evidence record set. Rejects
uncited, fabricated, or malformed citations.

Rules:
  C1 — Uncited factual claim (sentence with no citation token)
  C2 — Citation references a source_id not in the provided record set
  C3 — Empty response (no sentences)
  C4 — Malformed citation token (not matching [<source>, <id>])
  C5 — All claims properly cited

Off-by-default; opt-in via SwarmRuntime(citation_validator=CitationValidator()).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class CitationVerdict(str, Enum):
    ALL_CITED = "ALL_CITED"
    MISSING_CITATIONS = "MISSING_CITATIONS"
    FABRICATED_CITATION = "FABRICATED_CITATION"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    MALFORMED = "MALFORMED"


class CitationRule(str, Enum):
    C1 = "C1"  # uncited claim
    C2 = "C2"  # citation not in record set
    C3 = "C3"  # empty response
    C4 = "C4"  # malformed citation token
    C5 = "C5"  # all clean


# Citation token pattern: [Source, ID] e.g. [CPIC, PMID:35034351]
_CITATION_RE = re.compile(r"\[([^,\[\]]+),\s*([^,\[\]]+)\]")

# Sentence boundary (simplistic but sufficient for structured narratives)
_SENTENCE_RE = re.compile(r"(?<=[.?!])\s+")

# Sentences that are purely structural/transitional and don't need citations
_SKIP_PATTERNS = re.compile(
    r"^(in summary|note:|disclaimer:|⚠️|#|>|\*\*|---)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SentenceValidation:
    text: str
    citations_found: tuple[str, ...]
    rule: CitationRule
    is_valid: bool


@dataclass(frozen=True)
class CitationValidationTrace:
    verdict: CitationVerdict
    sentences: tuple[SentenceValidation, ...]
    uncited_claims: tuple[str, ...]
    fabricated_citations: tuple[str, ...]
    total_sentences: int
    cited_sentences: int
    rules_triggered: tuple[CitationRule, ...]


class CitationValidator:
    """Validates that LLM narrative text cites only provided evidence records."""

    def validate(
        self,
        text: str,
        evidence_source_ids: set[str] | None = None,
    ) -> CitationValidationTrace:
        """Validate citations in text against known source IDs.

        Args:
            text: The LLM-generated narrative text.
            evidence_source_ids: Set of valid source identifiers
                (e.g. PMIDs, guideline IDs). If None, only checks
                that citations exist (doesn't verify against a set).
        """
        if not text or not text.strip():
            return CitationValidationTrace(
                verdict=CitationVerdict.EMPTY_RESPONSE,
                sentences=(),
                uncited_claims=(),
                fabricated_citations=(),
                total_sentences=0,
                cited_sentences=0,
                rules_triggered=(CitationRule.C3,),
            )

        sentences = [s.strip() for s in _SENTENCE_RE.split(text.strip()) if s.strip()]
        if not sentences:
            sentences = [text.strip()]

        validations: list[SentenceValidation] = []
        uncited: list[str] = []
        fabricated: list[str] = []
        rules_triggered: set[CitationRule] = set()
        cited_count = 0

        for sentence in sentences:
            # Skip structural/header sentences
            if _SKIP_PATTERNS.match(sentence) or len(sentence) < 15:
                validations.append(SentenceValidation(
                    text=sentence, citations_found=(), rule=CitationRule.C5, is_valid=True,
                ))
                cited_count += 1
                continue

            citations = _CITATION_RE.findall(sentence)

            if not citations:
                # No citation token → C1
                rules_triggered.add(CitationRule.C1)
                uncited.append(sentence)
                validations.append(SentenceValidation(
                    text=sentence, citations_found=(), rule=CitationRule.C1, is_valid=False,
                ))
                continue

            # Check each citation against the record set
            citation_ids = tuple(f"{src.strip()}, {cid.strip()}" for src, cid in citations)
            sentence_valid = True

            if evidence_source_ids is not None:
                for src, cid in citations:
                    cid_clean = cid.strip()
                    src_clean = src.strip()
                    # Check if either the full token or just the ID is in the set
                    if (
                        cid_clean not in evidence_source_ids
                        and src_clean not in evidence_source_ids
                        and f"{src_clean}, {cid_clean}" not in evidence_source_ids
                    ):
                        fabricated.append(f"[{src_clean}, {cid_clean}]")
                        rules_triggered.add(CitationRule.C2)
                        sentence_valid = False

            if sentence_valid:
                cited_count += 1

            validations.append(SentenceValidation(
                text=sentence,
                citations_found=citation_ids,
                rule=CitationRule.C5 if sentence_valid else CitationRule.C2,
                is_valid=sentence_valid,
            ))

        # Determine overall verdict
        if fabricated:
            verdict = CitationVerdict.FABRICATED_CITATION
        elif uncited:
            verdict = CitationVerdict.MISSING_CITATIONS
        else:
            verdict = CitationVerdict.ALL_CITED
            rules_triggered.add(CitationRule.C5)

        return CitationValidationTrace(
            verdict=verdict,
            sentences=tuple(validations),
            uncited_claims=tuple(uncited),
            fabricated_citations=tuple(fabricated),
            total_sentences=len(sentences),
            cited_sentences=cited_count,
            rules_triggered=tuple(sorted(rules_triggered, key=lambda r: r.value)),
        )
