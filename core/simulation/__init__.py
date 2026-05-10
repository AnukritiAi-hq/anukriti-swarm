"""Anukriti Swarm — core/simulation/ package.

Stage 1 of the simulation research direction described in
``anukriti-pgx-core/docs/strategy.md``. **This package ships types
and contracts only — no engine yet.**

What lives here
---------------
Closed-enum types and frozen records for cohort-scale PGx reasoning
over synthetic populations drawn from real allele-frequency
distributions. This is explicitly not a PK/PD simulation layer
(that's Stage 3, years away); it's the *data contract* for
cohort-scale reasoning built on public/aggregate data (CPIC, 1000
Genomes super-population frequencies, IndiGen, GenomeAsia Pilot).

Why this package exists today
-----------------------------
Three reasons:

1. **Scope firewall extension.** Just as ``BiomedicalContextType``
   (interoperability) and ``SufficiencyDecision`` (evidence) are
   closed enums that make scope drift a compile-time event, this
   package establishes the closed types for simulation-scope work
   *before* the engine code lands. That way, when simulation work
   begins, the types are already reviewed and the scope is already
   bounded.

2. **Platform positioning.** Per ADR-0002 in anukriti-pgx-core, the
   platform is positioned as "evidence-governed drug safety
   infrastructure" with a roadmap toward population-scale
   computational inference. This package is the architectural
   commitment to that direction — visible in code, not just in
   strategy docs.

3. **Credibility for cohort-scale demos.** ``demos/cohort_demo.py``
   imports from here to build its 100-patient Monte Carlo. Without
   these types, the cohort demo would either invent its own types
   (scope-firewall hole) or operate at a lower level of rigor.

What does NOT live here
-----------------------
- A PK/PD simulation engine (Stage 3, years away, gated on Tier 3
  data access)
- A "virtual trials" replacement for actual clinical trials (we
  don't claim this and won't)
- Anything that requires individual-level controlled-access data
  (H3Africa, GenomeIndia, All of Us individual-level)

If a future feature needs any of those, it is out of scope for this
package. Adding it requires an ADR or a deliberate extension of
the closed enums below.

Stage-1 guarantee
-----------------
Everything here operates on **public or aggregate data only**:
- CPIC allele frequency tables (open-access)
- 1000 Genomes super-population frequencies (public)
- IndiGen (open/registered-access)
- GenomeAsia Pilot 2019 (published aggregate data)

See ``anukriti-pgx-core/docs/strategy.md`` for the tier framework.
"""

from __future__ import annotations

from core.simulation.types import (
    CohortSamplingMethod,
    DrugSafetyOutcome,
    SimulationRun,
    SimulationScope,
    SyntheticPatient,
    VirtualPopulation,
)

__all__ = [
    "CohortSamplingMethod",
    "DrugSafetyOutcome",
    "SimulationRun",
    "SimulationScope",
    "SyntheticPatient",
    "VirtualPopulation",
]
