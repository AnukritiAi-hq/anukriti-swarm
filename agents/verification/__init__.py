"""Anukriti Swarm — verification agent package.

This package was promoted from the single-file ``agents/verification.py``
so the deterministic safety engine (``core.verification``) can register
multiple verification agents without crowding one module.

Backward compatibility:
  ``from agents.verification import VerificationAgent``
is preserved by re-exporting the legacy class from ``legacy_agent``
so every existing caller keeps working unchanged. The legacy class is
kept intact for the ``workflows.pharmacogenomic_pipeline`` call site
that wires it into the LangGraph-style pipeline.

New-style callers use ``BiomedicalVerificationAgent`` (landing in a
follow-up commit) which composes the ``core.verification`` engines
and emits a list of ``VerificationTrace`` records per run.
"""

from __future__ import annotations

from agents.verification.legacy_agent import VerificationAgent

__all__ = ["VerificationAgent"]
