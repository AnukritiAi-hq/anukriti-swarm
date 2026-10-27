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
  C6 — Quantity stated that does not appear in the grounded context

C6 is the numeric-drift guard: a citation check cannot see a 50% dose
reduction rendered as 40%, because the sentence may be perfectly cited
and still carry the wrong number. It only runs when the caller passes
``grounded_context`` — with nothing to compare against, a quantity is
unverifiable, not wrong, so the rule stays silent rather than rejecting.

Only numbers carrying a clinically meaningful unit are checked. Numbers
with no unit are ignored because they cannot be told apart from PMIDs,
rsIDs, genomic positions and activity scores. Bare ``g`` and ``L`` are
not units here: HGVS notation puts a nucleotide straight after a digit,
so ``c.1905+1G>A`` would otherwise parse as one gram, and a guard that
fires on correct genomic notation gets switched off.

The same rule exists in the research sandbox as ``LV-QUANT`` in
``anukriti/src/llm_output_validator.py``. It is restated rather than
imported: that package is not a dependency of this one, and a shared
dependency for one regex would cost more than it saves.

Off-by-default; opt-in via SwarmRuntime(citation_validator=CitationValidator()).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class CitationVerdict(str, Enum):
    ALL_CITED = "ALL_CITED"
    MISSING_CITATIONS = "MISSING_CITATIONS"
    FABRICATED_CITATION = "FABRICATED_CITATION"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    MALFORMED = "MALFORMED"
    UNSUPPORTED_QUANTITY = "UNSUPPORTED_QUANTITY"


class CitationRule(str, Enum):
    C1 = "C1"  # uncited claim
    C2 = "C2"  # citation not in record set
    C3 = "C3"  # empty response
    C4 = "C4"  # malformed citation token
    C5 = "C5"  # all clean
    C6 = "C6"  # quantity absent from the grounded context


# Citation token pattern: [Source, ID] e.g. [CPIC, PMID:35034351]
_CITATION_RE = re.compile(r"\[([^,\[\]]+),\s*([^,\[\]]+)\]")

# Sentence boundary (simplistic but sufficient for structured narratives)
_SENTENCE_RE = re.compile(r"(?<=[.?!])\s+")

# Sentences that are purely structural/transitional and don't need citations
_SKIP_PATTERNS = re.compile(
    r"^(in summary|note:|disclaimer:|⚠️|#|>|\*\*|---)",
    re.IGNORECASE,
)

# Units that carry clinical meaning. See the module docstring for why bare
# g and L are absent.
_CLINICAL_UNITS: dict[str, str] = {
    "%": "%",
    "percent": "%",
    "mg/m2": "mg/m2",
    "mg/m²": "mg/m2",
    "mg/kg": "mg/kg",
    "mg": "mg",
    "mcg": "mcg",
    "µg": "mcg",
    "ug": "mcg",
    "ng": "ng",
    "ml": "ml",
    "iu": "iu",
    "units": "unit",
    "unit": "unit",
}

# Longest alternatives first so mg/m2 wins over mg. The trailing (?!\w) is
# not \b: a word boundary fails after "%" when the next character is also
# non-word, so "50%." would not match.
_QUANTITY_RE = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*"
    r"(%|percent|mg/m²|mg/m2|mg/kg|mg|mcg|µg|ug|ng|ml|iu|units|unit)"
    r"(?!\w)",
    re.IGNORECASE,
)

# Any numeric literal, for the weaker "was this value available at all" test.
_NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)")


def _normalize_number(raw: str) -> str:
    """50.0 and 50 are the same quantity; so are 1.50 and 1.5."""
    try:
        return f"{float(raw):g}"
    except (TypeError, ValueError):  # pragma: no cover — regex guarantees digits
        return raw


def _quantities(text: str) -> set[tuple[str, str]]:
    """(value, unit) pairs carrying a clinical unit."""
    out: set[tuple[str, str]] = set()
    for m in _QUANTITY_RE.finditer(text or ""):
        unit_key = m.group(2).lower().replace("²", "2")
        out.add((_normalize_number(m.group(1)), _CLINICAL_UNITS.get(unit_key, unit_key)))
    return out


def _numbers(text: str) -> set[str]:
    return {_normalize_number(m.group(1)) for m in _NUMBER_RE.finditer(text or "")}


def _format_quantity(value: str, unit: str) -> str:
    return f"{value}{unit}" if unit == "%" else f"{value} {unit}"


def unsupported_quantities(text: str, grounded_context: str) -> tuple[str, ...]:
    """Quantities in ``text`` whose value is absent from ``grounded_context``.

    Two chances to pass. An exact (value, unit) match is the strong one.
    Failing that, the bare value appearing anywhere in the context is
    accepted, because a unit often sits in a field name rather than beside
    the number. Only a value present nowhere is reported.
    """
    permitted_pairs = _quantities(grounded_context)
    permitted_numbers = _numbers(grounded_context)
    flagged = [
        _format_quantity(value, unit)
        for value, unit in sorted(_quantities(text))
        if (value, unit) not in permitted_pairs and value not in permitted_numbers
    ]
    return tuple(flagged)


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
    # Trailing default so existing positional construction is unaffected.
    unsupported_quantities: tuple[str, ...] = ()


class CitationValidator:
    """Validates that LLM narrative text cites only provided evidence records."""

    def validate(
        self,
        text: str,
        evidence_source_ids: set[str] | None = None,
        grounded_context: str | None = None,
    ) -> CitationValidationTrace:
        """Validate citations in text against known source IDs.

        Args:
            text: The LLM-generated narrative text.
            evidence_source_ids: Set of valid source identifiers
                (e.g. PMIDs, guideline IDs). If None, only checks
                that citations exist (doesn't verify against a set).
            grounded_context: The context block the model was given. When
                supplied, rule C6 rejects any quantity in ``text`` whose
                value appears nowhere in it. When None, C6 does not run —
                an unverifiable quantity is not a wrong one.
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
        bad_quantities: list[str] = []
        rules_triggered: set[CitationRule] = set()
        cited_count = 0

        for sentence in sentences:
            # C6 is checked before the structural skip below. A short
            # sentence needs no citation but can still carry a wrong dose:
            # "Reduce by 40%." is 14 characters.
            sentence_bad_q: tuple[str, ...] = ()
            if grounded_context is not None:
                sentence_bad_q = unsupported_quantities(sentence, grounded_context)
                if sentence_bad_q:
                    bad_quantities.extend(sentence_bad_q)
                    rules_triggered.add(CitationRule.C6)

            # Skip structural/header sentences
            if _SKIP_PATTERNS.match(sentence) or len(sentence) < 15:
                validations.append(
                    SentenceValidation(
                        text=sentence,
                        citations_found=(),
                        rule=CitationRule.C6 if sentence_bad_q else CitationRule.C5,
                        is_valid=not sentence_bad_q,
                    )
                )
                if not sentence_bad_q:
                    cited_count += 1
                continue

            citations = _CITATION_RE.findall(sentence)

            if not citations:
                # No citation token → C1
                rules_triggered.add(CitationRule.C1)
                uncited.append(sentence)
                validations.append(
                    SentenceValidation(
                        text=sentence,
                        citations_found=(),
                        rule=CitationRule.C1,
                        is_valid=False,
                    )
                )
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

            if sentence_valid and sentence_bad_q:
                # Properly cited and still carrying a number the context
                # never contained — exactly what C2 cannot see.
                sentence_valid = False
                rule = CitationRule.C6
            elif sentence_valid:
                rule = CitationRule.C5
            else:
                rule = CitationRule.C2

            if sentence_valid:
                cited_count += 1

            validations.append(
                SentenceValidation(
                    text=sentence,
                    citations_found=citation_ids,
                    rule=rule,
                    is_valid=sentence_valid,
                )
            )

        # Determine overall verdict
        if fabricated:
            verdict = CitationVerdict.FABRICATED_CITATION
        elif bad_quantities:
            # Above MISSING_CITATIONS: a stated number the context never
            # contained is a worse failure than a missing citation token.
            verdict = CitationVerdict.UNSUPPORTED_QUANTITY
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
            unsupported_quantities=tuple(dict.fromkeys(bad_quantities)),
        )
