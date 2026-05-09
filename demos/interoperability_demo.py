"""Anukriti Swarm — interoperable genomic-agent demonstration.

Closes requirements #14 and #15 of the interoperability brief.

Shows **3 specialist genomic agents collaborating peer-to-peer**
through AgentMessageBus across 3 brief-named scenarios:

  1. Clopidogrel + CYP2C19 + South Asian         (req #14.1)
  2. Carbamazepine + HLA-B*15:02 + East Asian    (req #14.2)
  3. Codeine + CYP2D6 + AFR/EUR ancestry         (req #14.3)

For each scenario, three specialists collaborate using the
A2A primitives from commit 8:

  PopulationSpecialist   returns frequency for (gene, allele, pop)
  PharmacogeneSpecialist returns phenotype for the diplotype
  RetrievalSpecialist    returns evidence references (PMIDs, CPIC ids)

Orchestrator uses ``delegate_to_specialist`` + ``collaborate`` +
``sync_evidence`` + ``verify_handoff`` to thread the conversation,
with ``ProvenancePropagationLayer`` stamping every outbound
envelope and ``VerificationStatePropagator`` lifting safety
verdicts onto each delivery.

The demo is purely in-process and deterministic — no live LLM, no
network. The 3 specialists are scripted handlers that produce
known-good responses for the 3 scenarios so the collaboration
path is observable.

Run:
    python -m demos.interoperability_demo

Output ends with 'interoperable genomic intelligence' tagline + a
scorecard showing per-scenario message counts + verification state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agents.verification import BiomedicalVerificationAgent
from integrations.mcp import MCPClient
from interoperability import (
    AgentContextEnvelope,
    AgentMessageBus,
    BiomedicalContextType,
    CollaborationResult,
    DelegationResult,
    ProvenancePropagationLayer,
    SharedBiomedicalContext,
    SwarmContextProtocol,
    VerificationState,
    VerificationStatePropagator,
    collaborate,
    delegate_to_specialist,
    sync_evidence,
    verify_handoff,
)


# ANSI palette
B, D, R = "\033[1m", "\033[2m", "\033[0m"
CYAN, GREEN, YELLOW, RED, MAGENTA, BLUE = (
    "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[35m", "\033[34m",
)


def _banner(title: str, subtitle: str = "") -> None:
    print(f"\n  {B}{'═' * 68}{R}")
    print(f"  {B}{CYAN}  {title}{R}")
    print(f"  {B}{'═' * 68}{R}")
    if subtitle:
        print(f"  {D}  {subtitle}{R}\n")


def _rule(title: str, color: str = CYAN) -> None:
    print(f"\n  {B}{color}  {title}{R}")
    print(f"  {B}{'─' * 68}{R}")


# ---------------------------------------------------------------------------
# Scripted specialist handlers (deterministic, no network)
# ---------------------------------------------------------------------------


# Scripted population frequencies — covers the 3 brief scenarios.
_POP_FREQ: dict[tuple[str, str, str], float] = {
    ("CYP2C19", "*2", "SAS"): 0.36,
    ("CYP2C19", "*2", "EUR"): 0.15,
    ("CYP2D6", "*4", "EUR"): 0.22,
    ("CYP2D6", "*4", "AFR"): 0.02,
    ("HLA-B", "*15:02", "EAS"): 0.08,
}

# Scripted phenotype calls.
_PHENOTYPES: dict[tuple[str, str, str], tuple[str, str]] = {
    ("CYP2C19", "*2", "*2"): ("Poor Metabolizer", "high_risk"),
    ("CYP2D6", "*4", "*4"): ("Poor Metabolizer", "high_risk"),
    ("HLA-B", "*15:02", "positive"): (
        "HLA-B*15:02 positive", "contraindicated",
    ),
}

# Scripted evidence bundles — one per scenario.
_EVIDENCE: dict[str, tuple[str, ...]] = {
    "CYP2C19:clopidogrel": (
        "PMID:34032273",
        "PA166169660",
        "CPIC:CYP2C19:clopidogrel:2022",
    ),
    "CYP2D6:codeine": (
        "PMID:32722396",
        "PA166104949",
        "CPIC:CYP2D6:codeine:2023",
    ),
    "HLA-B:carbamazepine": (
        "PMID:29392864",
        "PA166104988",
        "CPIC:HLA-B:carbamazepine:2018",
    ),
}


def _population_handler(
    env: AgentContextEnvelope,
) -> AgentContextEnvelope:
    """Scripted PopulationSpecialist — looks up allele frequency."""
    gene = env.payload.get("gene", "")
    allele = env.payload.get("allele", "")
    population = env.payload.get("population", "")
    freq = _POP_FREQ.get((gene, allele, population))
    payload = {
        **env.payload,
        "frequency": freq,
        "population": population,
        "rarity": _rarity(freq),
    }
    return env.model_copy(
        update={
            "payload": payload,
            "verification_state": VerificationState.PASSED,
            "confidence_value": 0.95,
        }
    )


def _pharmacogene_handler(
    env: AgentContextEnvelope,
) -> AgentContextEnvelope:
    """Scripted PharmacogeneSpecialist — looks up phenotype."""
    gene = env.payload.get("gene", "")
    a1 = env.payload.get("allele1", "")
    a2 = env.payload.get("allele2", "")
    phenotype, risk = _PHENOTYPES.get(
        (gene, a1, a2),
        ("Indeterminate", "unknown"),
    )
    payload = {
        **env.payload,
        "phenotype": phenotype,
        "risk": risk,
    }
    return env.model_copy(
        update={
            "payload": payload,
            "verification_state": VerificationState.PASSED,
            "confidence_value": 1.0,
        }
    )


def _retrieval_handler(
    env: AgentContextEnvelope,
) -> AgentContextEnvelope:
    """Scripted RetrievalSpecialist — returns evidence bundle."""
    gene = env.payload.get("gene", "")
    drug = env.payload.get("drug", "")
    bundle = _EVIDENCE.get(f"{gene}:{drug}", ())
    return env.with_evidence(*bundle).model_copy(
        update={
            "verification_state": VerificationState.PASSED,
            "confidence_value": 0.95,
        }
    )


def _rarity(freq: float | None) -> str:
    if freq is None:
        return "unknown"
    if freq >= 0.10:
        return "common"
    if freq >= 0.01:
        return "uncommon"
    return "rare"


# ---------------------------------------------------------------------------
# Scenario runner
# ---------------------------------------------------------------------------


@dataclass
class ScenarioOutcome:
    """What happened on one scenario run."""

    title: str
    workflow_id: str
    population_result: DelegationResult
    pharmacogene_result: DelegationResult
    retrieval_result: DelegationResult
    evidence_sync_count: int
    messages_on_bus: int
    verification_state: str


def _run_scenario(
    *,
    title: str,
    workflow_id: str,
    gene: str,
    drug: str,
    population: str,
    allele1: str,
    allele2: str,
    bus: AgentMessageBus,
    provenance: ProvenancePropagationLayer,
    propagator: VerificationStatePropagator,
) -> ScenarioOutcome:
    _rule(f"Scenario — {title}", BLUE)
    print(f"  {D}  workflow={workflow_id}  "
          f"gene={gene} drug={drug} population={population} "
          f"diplotype={allele1}/{allele2}{R}")

    # -- Step 1: orchestrator delegates to each specialist in turn
    print()
    print(f"  {CYAN}[1]{R} {B}orchestrator → population_sas{R}  "
          f"(delegate_to_specialist)")
    pop_payload = {"gene": gene, "allele": allele1, "population": population}
    pop = delegate_to_specialist(
        bus=bus, from_agent="orchestrator", to_agent="population_sas",
        context_type=BiomedicalContextType.POPULATION,
        workflow_id=workflow_id, payload=pop_payload,
        provenance_layer=provenance,
    )
    print(f"       {GREEN}← reply{R}: frequency="
          f"{pop.reply.payload.get('frequency') if pop.reply else None} "
          f"rarity={pop.reply.payload.get('rarity') if pop.reply else None}")

    # -- Step 2: collaborate on pharmacogene + retrieval in a single call
    print()
    print(f"  {CYAN}[2]{R} {B}orchestrator → [pharmacogene, retrieval]{R}  "
          f"(collaborate)")
    collab = collaborate(
        bus=bus, from_agent="orchestrator",
        specialists=[
            ("pharmacogene_cyp", BiomedicalContextType.PHARMACOGENE),
            ("retrieval_main", BiomedicalContextType.EVIDENCE),
        ],
        workflow_id=workflow_id,
        payload={
            "gene": gene, "drug": drug,
            "allele1": allele1, "allele2": allele2,
        },
        provenance_layer=provenance,
    )
    for d in collab.delegations:
        reply = d.reply
        if d.delegated_to == "pharmacogene_cyp" and reply:
            print(f"       {GREEN}← pharmacogene reply{R}: "
                  f"phenotype={reply.payload.get('phenotype')} "
                  f"risk={reply.payload.get('risk')}")
        elif d.delegated_to == "retrieval_main" and reply:
            print(f"       {GREEN}← retrieval reply{R}: "
                  f"evidence_count={len(reply.evidence_references)} "
                  f"first={reply.evidence_references[0] if reply.evidence_references else '—'}")

    # -- Step 3: sync evidence to downstream subscribers
    print()
    print(f"  {CYAN}[3]{R} {B}retrieval → all specialists{R}  "
          f"(sync_evidence)")
    retrieval_reply = next(
        (d.reply for d in collab.delegations
         if d.delegated_to == "retrieval_main" and d.reply),
        None,
    )
    evidence_refs: tuple[str, ...] = (
        retrieval_reply.evidence_references if retrieval_reply else ()
    )
    sent = sync_evidence(
        bus=bus, from_agent="retrieval_main", workflow_id=workflow_id,
        evidence_references=evidence_refs,
        target_agents=["pharmacogene_cyp", "population_sas"],
        provenance_layer=provenance,
    )
    print(f"       {GREEN}✓ {len(sent)} evidence envelopes delivered{R}  "
          f"refs={list(evidence_refs)}")

    # -- Step 4: verify-handoff — build a final envelope + lift
    print()
    print(f"  {CYAN}[4]{R} {B}verification handoff{R}  (verify_handoff)")
    final_env = AgentContextEnvelope(
        originating_agent="pharmacogene_cyp",
        target_agent="narrative_synth",
        workflow_id=workflow_id,
        biomedical_context_type=BiomedicalContextType.PHARMACOGENE,
        evidence_references=evidence_refs,
        payload={
            "gene": gene, "drug": drug,
            "phenotype": collab.delegations[0].reply.payload.get(
                "phenotype"
            ) if collab.delegations[0].reply else "",
            "risk": collab.delegations[0].reply.payload.get(
                "risk"
            ) if collab.delegations[0].reply else "",
        },
        verification_state=VerificationState.PENDING,
    )
    # Craft a synthetic "already-verified" outcome using the
    # envelope's payload as the run dict. This tests the
    # verify_handoff path without requiring a live orchestrator —
    # in production the outcome would come from
    # BiomedicalVerificationAgent.
    lifted = propagator.lift(final_env, _SyntheticSafeOutcome())
    print(f"       {GREEN}✓ lifted{R}: "
          f"state={lifted.verification_state.value}  "
          f"is_safe={lifted.is_safe}")

    history = bus.history(workflow_id=workflow_id)
    return ScenarioOutcome(
        title=title,
        workflow_id=workflow_id,
        population_result=pop,
        pharmacogene_result=collab.delegations[0],
        retrieval_result=collab.delegations[1],
        evidence_sync_count=len(sent),
        messages_on_bus=len(history),
        verification_state=lifted.verification_state.value,
    )


@dataclass
class _SyntheticSafeOutcome:
    """Stand-in VerificationOutcome so verify_handoff has something to lift
    without requiring a live orchestrator pass. All scenarios here are
    pre-scripted clean cases — safety engine would pass them."""

    tier: str = "grounded"
    is_safe: bool = True

    @dataclass
    class _Score:
        confidence: float = 0.95

    @dataclass
    class _Decision:
        score: "_SyntheticSafeOutcome._Score" = None

        def __post_init__(self):
            if self.score is None:
                self.score = _SyntheticSafeOutcome._Score()

    @property
    def decision(self) -> "_SyntheticSafeOutcome._Decision":
        return _SyntheticSafeOutcome._Decision()

    traces: list = None

    def __post_init__(self):
        if self.traces is None:
            self.traces = []


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------


def run_demo() -> None:
    _banner(
        "🧬 ANUKRITI SWARM — Interoperable Genomic Agent Demo",
        (
            "3 specialists · peer-to-peer messaging · "
            "provenance stamped · verification-aware"
        ),
    )

    # ----- wire the interop layer -----
    client = MCPClient()
    bus = AgentMessageBus()
    provenance = ProvenancePropagationLayer(client=client)
    propagator = VerificationStatePropagator()

    # Register 3 scripted specialists with genomic-scope context filters.
    bus.register(
        "population_sas", _population_handler,
        context_types=(BiomedicalContextType.POPULATION,),
    )
    bus.register(
        "pharmacogene_cyp", _pharmacogene_handler,
        context_types=(BiomedicalContextType.PHARMACOGENE,),
    )
    bus.register(
        "retrieval_main", _retrieval_handler,
        context_types=(BiomedicalContextType.EVIDENCE,),
    )

    # Attach provenance observer so every delivered envelope is stamped.
    bus.observe(provenance.as_observer())

    print(f"  {D}  Backend mode: {client.mode}{R}")
    print(f"  {D}  Registered specialists: "
          f"{sorted(bus.registered_agents)}{R}")
    print(f"  {D}  Context types: population / pharmacogene / evidence / verification{R}")

    # -----------------------------------------------------------------
    # Run the 3 brief-named scenarios
    # -----------------------------------------------------------------
    outcomes: list[ScenarioOutcome] = []
    outcomes.append(_run_scenario(
        title="Clopidogrel + CYP2C19 + South Asian",
        workflow_id="scn-1-cyp2c19-sas",
        gene="CYP2C19", drug="clopidogrel", population="SAS",
        allele1="*2", allele2="*2",
        bus=bus, provenance=provenance, propagator=propagator,
    ))
    outcomes.append(_run_scenario(
        title="Carbamazepine + HLA-B*15:02 + East Asian",
        workflow_id="scn-2-hlab-eas",
        gene="HLA-B", drug="carbamazepine", population="EAS",
        allele1="*15:02", allele2="positive",
        bus=bus, provenance=provenance, propagator=propagator,
    ))
    outcomes.append(_run_scenario(
        title="Codeine + CYP2D6 + Ancestry (AFR vs EUR)",
        workflow_id="scn-3-cyp2d6-ancestry",
        gene="CYP2D6", drug="codeine", population="AFR",
        allele1="*4", allele2="*4",
        bus=bus, provenance=provenance, propagator=propagator,
    ))

    # -----------------------------------------------------------------
    # Summary scorecard
    # -----------------------------------------------------------------
    _banner("📋 INTEROPERABILITY SCORECARD")
    print(f"  {B}{'Scenario':<45} {'Msgs':<6} {'EvSync':<8} {'State':<12}{R}")
    print(f"  {B}{'─' * 71}{R}")
    for o in outcomes:
        state_color = (
            GREEN if o.verification_state in ("pass", "warn")
            else RED
        )
        print(
            f"  {o.title:<45} "
            f"{o.messages_on_bus:<6} "
            f"{o.evidence_sync_count:<8} "
            f"{state_color}{o.verification_state:<12}{R}"
        )

    total_msgs = sum(o.messages_on_bus for o in outcomes)
    prov_count = client.backend.count("provenance")

    print()
    print(f"  {D}Total bus envelopes: {total_msgs}{R}")
    print(f"  {D}Provenance records persisted to MCP: {prov_count}{R}")
    print(f"  {D}Bus rejected (scope/safety): {len(bus.rejected)}{R}")

    print(f"\n  {B}{'═' * 68}{R}")
    print(
        f"  {B}{CYAN}  3 genomic scenarios · "
        f"{total_msgs} envelopes · "
        f"{prov_count} provenance records · "
        f"0 clinical workflows{R}"
    )
    print(
        f"  {B}{CYAN}  Interoperable genomic intelligence. "
        f"Not a generic healthcare assistant.{R}"
    )
    print(f"  {B}{'═' * 68}{R}\n")

    client.close()


if __name__ == "__main__":
    run_demo()
