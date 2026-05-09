"""Legacy phenotype-rules entry point — now a shim over anukriti-pgx-core.

History
-------
Before Phase 1 of the anukriti-pgx-core extraction, this module was the
authoritative deterministic phenotype inference layer. It held:

  - ALLELE_ACTIVITY_SCORES     dict[gene, dict[allele, score]]
  - PHENOTYPE_RANGES           dict[gene, list[tuple[low, high, phenotype]]]
  - NAMED_DIPLOTYPES           dict[gene, dict[diplotype, phenotype]]
  - infer_phenotype()          main call
  - get_activity_score()       single-allele lookup
  - PhenotypeInference         frozen dataclass

All of that logic and data now lives in the ``anukriti-pgx-core`` package:

  - ``anukriti_pgx_core.phenotype.PhenotypeEngine``
  - ``anukriti_pgx_core.types.PhenotypeInference``
  - pinned JSON tables in ``anukriti_pgx_core/phenotype/tables/``

This module stays as a thin re-export so existing swarm-side consumers
(agents/pharmacogene/base.py, core/verification/safety.py,
core/runtime/runtime.py, tests, any future imports) don't need to change
during the migration. When swarm-side call sites all import from
``anukriti_pgx_core`` directly, this file can be deleted without
touching any of them.

Behaviour is byte-identical:
  - Same ``PhenotypeInference`` return shape (with two additional
    provenance fields, ``cpic_table_version`` and ``pgx_core_version``,
    that are populated but default-empty so unpacking-style code stays
    safe).
  - Same ``rule_version`` string (``cpic_activity_score_v2``).
  - Same dispatch order (named-diplotype lookup first for CYP2C19,
    additive activity-score fallback otherwise).
"""

from __future__ import annotations

from anukriti_pgx_core import PhenotypeEngine
from anukriti_pgx_core.types import PhenotypeInference

# Singleton engine. Loading the pinned JSON tables happens once at
# import time, identical to how the old module's module-level dicts
# were populated once.
_ENGINE = PhenotypeEngine()


# ---------------------------------------------------------------------------
# Re-exported public surface (preserved from the pre-extraction module)
# ---------------------------------------------------------------------------


def infer_phenotype(gene: str, allele1: str, allele2: str) -> PhenotypeInference:
    """Deterministic phenotype inference. See PhenotypeEngine.infer."""
    return _ENGINE.infer(gene, allele1, allele2)


def get_activity_score(gene: str, allele: str) -> float | None:
    """Return the activity score for an allele, or None if unknown."""
    return _ENGINE.activity_score(gene, allele)


# Snapshot of the activity-score tables. ``safety.py`` reads this dict
# directly (membership checks on ALLELE_ACTIVITY_SCORES[gene]); keeping
# the same shape means no changes are needed there.
ALLELE_ACTIVITY_SCORES: dict[str, dict[str, float]] = (
    _ENGINE.activity_scores_snapshot()
)


__all__ = [
    "PhenotypeInference",
    "infer_phenotype",
    "get_activity_score",
    "ALLELE_ACTIVITY_SCORES",
]
