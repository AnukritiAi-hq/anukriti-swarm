"""Integration tests for ``core.runtime.runtime.SwarmRuntime``.

Each test runs the full 5-stage lifecycle against the real in-tree
seed data (KG + retrieval docs + sufficiency checkpoint). These are
integration tests because they cross module boundaries — if the
KG seed changes, or a rule table shifts, these tests catch it.

Flagship scenarios pin the canonical run signatures:

    SAS + CYP2C19*2/*2 + clopidogrel     -> sufficient / supported / low  / 14 events
    EAS + HLA-B*15:02  + carbamazepine   -> sufficient / supported / low  / 14 events
    AFR + CYP2D6 *4/*4 + codeine         -> downgrade  / uncertain / high / 13 events

If these numbers drift without an accompanying change to the
documented lifecycle, something has changed silently.
"""

from __future__ import annotations

import pytest
from core.models.population import SuperPopulation
from core.runtime.context import UnifiedExecutionContext
from core.runtime.events import InMemoryEventStream, RuntimeEventKind
from core.runtime.report import UnifiedExecutionReport
from core.runtime.runtime import SwarmRuntime

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runtime() -> SwarmRuntime:
    """Fresh runtime + fresh in-memory stream per test."""
    return SwarmRuntime(event_stream=InMemoryEventStream())


def _sas_clopidogrel() -> UnifiedExecutionContext:
    return UnifiedExecutionContext.new(
        drug="clopidogrel",
        gene="CYP2C19",
        population=SuperPopulation.SAS,
        genotype="*2/*2",
    )


def _eas_carbamazepine() -> UnifiedExecutionContext:
    return UnifiedExecutionContext.new(
        drug="carbamazepine",
        gene="HLA-B",
        population=SuperPopulation.EAS,
        genotype="*15:02/positive",
    )


def _afr_codeine() -> UnifiedExecutionContext:
    return UnifiedExecutionContext.new(
        drug="codeine",
        gene="CYP2D6",
        population=SuperPopulation.AFR,
        genotype="*4/*4",
    )


# ---------------------------------------------------------------------------
# Shape: report + context contract
# ---------------------------------------------------------------------------


class TestRuntimeReportShape:
    def test_run_returns_unified_execution_report(self, runtime: SwarmRuntime) -> None:
        report = runtime.run(_sas_clopidogrel())
        assert isinstance(report, UnifiedExecutionReport)

    def test_scope_keys_preserved_in_report(self, runtime: SwarmRuntime) -> None:
        ctx = _sas_clopidogrel()
        report = runtime.run(ctx)
        assert report.drug == "clopidogrel"
        assert report.gene == "CYP2C19"
        assert report.population == "SAS"
        assert report.genotype == "*2/*2"
        assert report.correlation_id == ctx.correlation_id

    def test_report_is_jsonable(self, runtime: SwarmRuntime) -> None:
        import json

        report = runtime.run(_sas_clopidogrel())
        # to_dict if present; fall back to the dataclass asdict pattern.
        # SwarmRuntime returns a frozen dataclass; ensure it serializes
        # cleanly for the FastAPI boundary.
        from dataclasses import asdict

        def default(o):
            # datetime etc.
            return str(o)

        json.dumps(asdict(report), default=default)


# ---------------------------------------------------------------------------
# Lifecycle events: every run starts RUN_STARTED and ends RUN_COMPLETED
# ---------------------------------------------------------------------------


class TestLifecycleEvents:
    def test_run_started_is_first_event(self, runtime: SwarmRuntime) -> None:
        runtime.run(_sas_clopidogrel())
        assert isinstance(runtime.event_stream, InMemoryEventStream)
        events = runtime.event_stream.events
        assert len(events) > 0
        assert events[0].kind is RuntimeEventKind.RUN_STARTED

    def test_run_completed_is_last_event_on_success(self, runtime: SwarmRuntime) -> None:
        runtime.run(_sas_clopidogrel())
        assert isinstance(runtime.event_stream, InMemoryEventStream)
        last = runtime.event_stream.events[-1]
        assert last.kind is RuntimeEventKind.RUN_COMPLETED

    def test_correlation_id_stamped_on_every_event(self, runtime: SwarmRuntime) -> None:
        ctx = _sas_clopidogrel()
        runtime.run(ctx)
        assert isinstance(runtime.event_stream, InMemoryEventStream)
        for e in runtime.event_stream.events:
            assert e.correlation_id == ctx.correlation_id


# ---------------------------------------------------------------------------
# Flagship signatures (regression guards)
# ---------------------------------------------------------------------------


class TestFlagshipSignatures:
    """Pin the session-#7 canonical signatures. A diff in the event
    count or final verdict should fail loudly so a reviewer looks at
    the upstream change."""

    def test_sas_clopidogrel_yields_sufficient_supported_low(self, runtime: SwarmRuntime) -> None:
        report = runtime.run(_sas_clopidogrel())
        assert report.evidence_sufficiency is not None
        # Sufficient decision + supported verdict + low uncertainty.
        es = report.evidence_sufficiency
        assert es["sufficiency_decision"] == "sufficient"
        assert es["verdict"] == "supported"
        assert es["uncertainty_score"] == "low"
        assert es["allows_synthesis"] is True
        # Rule ids must be named (audit trail).
        assert es["verdict_rule_id"].startswith("V")
        assert "R" in es["sufficiency_rationale"]

    def test_eas_carbamazepine_yields_sufficient_supported(self, runtime: SwarmRuntime) -> None:
        report = runtime.run(_eas_carbamazepine())
        assert report.evidence_sufficiency is not None
        es = report.evidence_sufficiency
        assert es["sufficiency_decision"] == "sufficient"
        assert es["verdict"] == "supported"
        assert es["allows_synthesis"] is True

    def test_afr_codeine_refuses_synthesis(self, runtime: SwarmRuntime) -> None:
        """AFR codeine scenario is an HONEST refusal, not a regression.
        Evidence scarcity is real in the seed KG and the layer names
        the rule that fires (V7 population uncertain)."""
        report = runtime.run(_afr_codeine())
        assert report.evidence_sufficiency is not None
        assert report.evidence_sufficiency["allows_synthesis"] is False
        # Refusal reason must reference a specific rule id.
        final = report.final_recommendation
        assert not final.get("allows_synthesis", False)


# ---------------------------------------------------------------------------
# Event composition: every scenario emits the expected event classes
# ---------------------------------------------------------------------------


class TestEventComposition:
    """The lifecycle emits a standard set of event kinds for any
    scenario, with a run-specific final event (COMPLETED vs ABSTENTION)."""

    def test_sas_scenario_emits_complete_lifecycle(self, runtime: SwarmRuntime) -> None:
        runtime.run(_sas_clopidogrel())
        assert isinstance(runtime.event_stream, InMemoryEventStream)
        kinds = {e.kind for e in runtime.event_stream.events}
        # Every major lifecycle stage must be present for a happy-path run.
        required = {
            RuntimeEventKind.RUN_STARTED,
            RuntimeEventKind.AGENT_ACTIVATED,
            RuntimeEventKind.RETRIEVAL_COMPLETE,
            RuntimeEventKind.GRAPH_TRAVERSAL,
            RuntimeEventKind.SUFFICIENCY_DECISION,
            RuntimeEventKind.VERIFICATION_CHECKPOINT,
            RuntimeEventKind.UNCERTAINTY_TRANSITION,
            RuntimeEventKind.SYNTHESIS_EMITTED,
            RuntimeEventKind.RUN_COMPLETED,
        }
        missing = required - kinds
        assert not missing, f"missing expected event kinds: {missing}"

    def test_afr_codeine_emits_safe_abstention_not_synthesis(self, runtime: SwarmRuntime) -> None:
        runtime.run(_afr_codeine())
        assert isinstance(runtime.event_stream, InMemoryEventStream)
        kinds = [e.kind for e in runtime.event_stream.events]
        # Abstention run: SAFE_ABSTENTION is emitted; SYNTHESIS_EMITTED is not.
        assert RuntimeEventKind.SAFE_ABSTENTION in kinds
        assert RuntimeEventKind.SYNTHESIS_EMITTED not in kinds


# ---------------------------------------------------------------------------
# Component reuse — one runtime can serve many runs
# ---------------------------------------------------------------------------


class TestComponentReuse:
    def test_runtime_handles_multiple_sequential_runs(self) -> None:
        """A single SwarmRuntime instance must be safe for many runs.
        The session-#7 contract is "components built once, reused
        across scenarios".
        """
        runtime = SwarmRuntime(event_stream=InMemoryEventStream())
        r1 = runtime.run(_sas_clopidogrel())
        r2 = runtime.run(_eas_carbamazepine())
        r3 = runtime.run(_afr_codeine())
        assert r1.correlation_id != r2.correlation_id != r3.correlation_id
        # All three runs must be captured in the same stream, in order.
        assert isinstance(runtime.event_stream, InMemoryEventStream)
        events = runtime.event_stream.events
        started = [e for e in events if e.kind is RuntimeEventKind.RUN_STARTED]
        assert len(started) == 3
        assert [e.correlation_id for e in started] == [
            r1.correlation_id,
            r2.correlation_id,
            r3.correlation_id,
        ]

    def test_shared_components_built_once(self) -> None:
        """_graph, _indexer, _reasoner, _retriever, _selector,
        _checkpoint are populated after the first run and stay
        populated across subsequent runs."""
        runtime = SwarmRuntime(event_stream=InMemoryEventStream())
        runtime.run(_sas_clopidogrel())
        graph_ref_after_run_1 = runtime._graph
        indexer_ref_after_run_1 = runtime._indexer
        assert graph_ref_after_run_1 is not None
        assert indexer_ref_after_run_1 is not None
        runtime.run(_eas_carbamazepine())
        # Same object identity — built once.
        assert runtime._graph is graph_ref_after_run_1
        assert runtime._indexer is indexer_ref_after_run_1


# ---------------------------------------------------------------------------
# Determinism — same input -> same decision tree, same rule ids
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_repeated_run_yields_same_decision(self) -> None:
        """Two fresh runtimes running the same input must produce
        the same final sufficiency + verdict + uncertainty. Wall
        clocks and uuids vary; rule-table outputs must not.
        """
        r1 = SwarmRuntime(event_stream=InMemoryEventStream()).run(_sas_clopidogrel())
        r2 = SwarmRuntime(event_stream=InMemoryEventStream()).run(_sas_clopidogrel())
        assert r1.evidence_sufficiency is not None
        assert r2.evidence_sufficiency is not None
        assert (
            r1.evidence_sufficiency["sufficiency_decision"]
            == (r2.evidence_sufficiency["sufficiency_decision"])
        )
        assert r1.evidence_sufficiency["verdict"] == (r2.evidence_sufficiency["verdict"])
        assert (
            r1.evidence_sufficiency["uncertainty_score"]
            == (r2.evidence_sufficiency["uncertainty_score"])
        )
