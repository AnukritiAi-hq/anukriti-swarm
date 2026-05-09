"""Evidence Sufficiency — ``conflict/`` subpackage.

Hosts ``ConflictDetectionAgent`` — a deterministic checker that looks
across the retrieved evidence set for contradictory signals before
synthesis runs.

The agent is *not* a general claim-reasoner. It detects exactly three
pharmacogenomic conflict classes:

    1. Phenotype disagreement   two sources predict different
                                metabolizer phenotypes for the same
                                diplotype in the same population
    2. Recommendation clash     two guideline sources recommend
                                incompatible actions for the same
                                drug-gene-phenotype tuple
    3. Population divergence    a claim's cited sources report
                                materially different allele
                                frequencies in the same ancestry
                                group (beyond declared tolerance)

If a conflict is detected, downstream synthesis is blocked and the
escalation workflow is invoked — same pattern as
``EscalationWorkflow`` in ``core.verification``.
"""

from __future__ import annotations

__all__: list[str] = []
