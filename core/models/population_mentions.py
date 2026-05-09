"""Shared super-population mention anchors.

Single source of truth for "does this piece of text mention a given
super-population?". Used by:

    core.evidence_sufficiency.coverage.analyzer
    retrieval.multi_strategy.biomedical_retriever

Centralising the anchor table keeps the two components in sync; a
change here touches both consumers under a single commit and the
scope firewall stays visible on the table itself.

The table is **closed**. Adding or renaming an anchor is a code
change — callers cannot extend at runtime.

Matching
--------
Short anchors (≤4 characters, e.g. 'afr', 'eas') are matched with
word-boundary regex so they do not false-positive inside English
words ('increased', 'disease', 'caucasian', …). Longer anchors
are matched as case-insensitive substrings — 'south asian' never
appears inside another word, and the substring match is stable
across whitespace/punctuation.

Why live under ``core.models`` ?
  Population mention is a property of the population domain, not of
  retrieval or of evidence; it belongs next to ``SuperPopulation``.
"""

from __future__ import annotations

import re

from core.models.population import SuperPopulation

# ---------------------------------------------------------------------------
# Closed anchor table
# ---------------------------------------------------------------------------


# Lowercase; the matcher lowercases inputs. Ordering within a
# population's tuple doesn't affect behaviour — we use ``any``.
POPULATION_MENTIONS: dict[SuperPopulation, tuple[str, ...]] = {
    SuperPopulation.AFR: ("afr", "african", "sub-saharan"),
    SuperPopulation.AMR: ("amr", "admixed american", "latino", "hispanic"),
    SuperPopulation.EAS: (
        "eas",
        "east asian",
        "southeast asian",
        "chinese",
        "japanese",
        "korean",
    ),
    SuperPopulation.EUR: ("eur", "european", "caucasian"),
    SuperPopulation.SAS: ("sas", "south asian", "indian", "pakistani"),
}


# Short anchors need \b word-boundaries so 'eas' doesn't match
# 'increased'. Threshold chosen so the 3-letter super-population
# codes are covered; all longer phrases are unambiguous.
_SHORT_ANCHOR_MAX_LEN = 4


def _matches_anchor(text_lower: str, anchor: str) -> bool:
    """Match a single anchor against already-lowercased text.

    Short anchors use \\b boundaries; longer anchors use substring.
    """

    if len(anchor) <= _SHORT_ANCHOR_MAX_LEN:
        # \b in a regex matches word/non-word transitions. re.escape
        # keeps literal anchor semantics if future anchors ever gain
        # punctuation.
        return re.search(rf"\b{re.escape(anchor)}\b", text_lower) is not None
    return anchor in text_lower


def mentions_population(text: str, population: SuperPopulation) -> bool:
    """Return True iff ``text`` contains any closed anchor for ``population``.

    Case-insensitive. Empty or None text returns False. Short
    anchors (≤4 chars) require word boundaries; longer anchors are
    matched as substrings — see module docstring.
    """

    if not text:
        return False
    lowered = text.lower()
    return any(
        _matches_anchor(lowered, anchor) for anchor in POPULATION_MENTIONS[population]
    )


__all__ = ["POPULATION_MENTIONS", "mentions_population"]
