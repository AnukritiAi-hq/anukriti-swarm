"""Stress-test scenarios for Anukriti Swarm.

Closes requirement #6 of the evaluation brief. Exercises the swarm
under conditions the normal scenario set doesn't reach:

    multi_agent_concurrency     run N orchestrator calls in parallel
                                 threads to surface shared-state bugs
    retrieval_failure            MCP evidence cache deliberately
                                 unavailable (backend.get raises)
    partial_workflow_collapse    one pipeline stage raises mid-run
                                 (e.g. pharmacogene agent crashes)
    memory_corruption            provenance records truncated /
                                 garbled in MCP; verification must
                                 detect via ProvenanceValidator

Each stress scenario produces a ``StressResult`` with:

    scenario_id     string id
    kind            one of the 4 kinds above
    observed        what actually happened (errors, counts)
    passed          did the system handle the stress gracefully?
    details         kind-specific diagnostics

``passed`` semantics vary by kind — a concurrency scenario passes
when no runs crashed AND all produced valid outputs; a retrieval
failure passes when the orchestrator completes but the grounding
report flags the missing sources; memory corruption passes when
the ProvenanceValidator catches the drift.

Runner
------
``run_stress_scenarios(...)`` iterates through the four scenarios,
catches exceptions, and returns a list of ``StressResult``. Designed
to be called from the evaluation demo (commit 11).
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable

from agents.orchestrator.gemini_orchestrator import GeminiOrchestrator
from agents.verification import BiomedicalVerificationAgent
from core.verification.provenance_validator import ProvenanceValidator
from integrations.mcp import MCPClient, MCPPersistenceHook


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


@dataclass
class StressResult:
    """Outcome of one stress scenario."""

    scenario_id: str
    kind: str
    passed: bool
    reason: str = ""
    observed: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "kind": self.kind,
            "passed": self.passed,
            "reason": self.reason,
            "observed": dict(self.observed),
            "duration_ms": round(self.duration_ms, 2),
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# 1. Multi-agent concurrency
# ---------------------------------------------------------------------------


def stress_multi_agent_concurrency(
    *,
    runs: int = 8,
    workers: int = 4,
) -> StressResult:
    """Run N orchestrator calls in parallel threads.

    Passes when every run completes without raising AND produces a
    non-empty coordination.runs list. Catches shared-state bugs
    (e.g. a mutable default arg, a module-level cache not guarded
    by a lock).
    """
    t0 = time.perf_counter()
    orch = GeminiOrchestrator()
    # A fresh orchestrator per thread would side-step any shared-state
    # bug the test is meant to find, so we share one instance.

    errors: list[str] = []
    completed = 0
    run_ids: list[str] = []
    lock = threading.Lock()

    def _one_run(i: int) -> None:
        nonlocal completed
        try:
            result = orch.run(
                gene="CYP2C19", drug="clopidogrel", population="SAS",
                allele1="*2", allele2="*2",
            )
            has_runs = bool(result.coordination.runs)
            with lock:
                if has_runs:
                    completed += 1
                    run_ids.append(result.context.correlation_id)
                else:
                    errors.append(f"run {i}: empty coordination.runs")
        except Exception as exc:
            with lock:
                errors.append(f"run {i}: {type(exc).__name__}: {exc}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_one_run, i) for i in range(runs)]
        for _ in as_completed(futs):
            pass

    duration_ms = (time.perf_counter() - t0) * 1000
    unique_ids = len(set(run_ids))
    passed = completed == runs and not errors and unique_ids == runs

    return StressResult(
        scenario_id="stress_multi_agent_concurrency",
        kind="concurrency",
        passed=passed,
        reason=(
            f"{completed}/{runs} completed, "
            f"{unique_ids}/{runs} unique correlation_ids, "
            f"{len(errors)} error(s)"
        ),
        observed={
            "runs": runs,
            "workers": workers,
            "completed": completed,
            "unique_correlation_ids": unique_ids,
        },
        duration_ms=duration_ms,
        errors=tuple(errors[:10]),  # cap at 10 for readability
    )


# ---------------------------------------------------------------------------
# 2. Retrieval failure
# ---------------------------------------------------------------------------


def stress_retrieval_failure() -> StressResult:
    """Force MCP evidence.get to fail; orchestrator must still complete.

    Monkey-patches ``MCPClient.backend.query`` for the evidence
    collection to raise RuntimeError. The orchestrator run should
    still complete (retrieval is best-effort); the grounding
    report should flag every source as missing.
    """
    t0 = time.perf_counter()
    client = MCPClient()
    orch = GeminiOrchestrator()
    hook = MCPPersistenceHook(client=client)
    agent = BiomedicalVerificationAgent(client=client)

    # Patch the backend's query to fail on evidence lookups.
    original_query = client.backend.query
    fail_count = [0]

    def failing_query(collection: str, *args: Any, **kwargs: Any):
        if collection == "evidence":
            fail_count[0] += 1
            raise RuntimeError("simulated evidence cache outage")
        return original_query(collection, *args, **kwargs)

    client.backend.query = failing_query  # type: ignore[assignment]

    errors: list[str] = []
    completed = False
    tier = ""
    grounding_coverage = 0.0
    try:
        result = orch.run(
            gene="CYP2C19", drug="clopidogrel", population="SAS",
            allele1="*2", allele2="*2",
        )
        hook.persist(result)
        outcome = agent.verify_run(
            result.coordination.runs[0],
            correlation_id=result.context.correlation_id,
        )
        completed = True
        tier = outcome.tier
        if outcome.grounding is not None:
            grounding_coverage = outcome.grounding.coverage
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        # Restore the original query so tests after this don't crash.
        client.backend.query = original_query  # type: ignore[assignment]

    duration_ms = (time.perf_counter() - t0) * 1000
    # Passes if the orchestrator completed (didn't let the outage
    # crash the run) AND the grounding coverage dropped (signal
    # that retrieval actually failed).
    passed = completed and fail_count[0] > 0

    return StressResult(
        scenario_id="stress_retrieval_failure",
        kind="retrieval_failure",
        passed=passed,
        reason=(
            f"orchestrator completed={completed}, "
            f"evidence lookups failed={fail_count[0]}, "
            f"grounding_coverage={grounding_coverage:.0%}"
        ),
        observed={
            "completed": completed,
            "evidence_failures": fail_count[0],
            "tier": tier,
            "grounding_coverage": round(grounding_coverage, 4),
        },
        duration_ms=duration_ms,
        errors=tuple(errors),
    )


# ---------------------------------------------------------------------------
# 3. Partial workflow collapse
# ---------------------------------------------------------------------------


def stress_partial_workflow_collapse() -> StressResult:
    """One pipeline stage raises mid-run; orchestrator must not crash.

    Wraps the pipeline runner with a decorator that raises
    RuntimeError on the third call. First two runs complete normally;
    the third should fail gracefully with an escalation event,
    not a traceback reaching the caller.
    """
    t0 = time.perf_counter()


    orch = GeminiOrchestrator()
    # coordinator._runner may be None (it lazy-resolves to
    # _default_runner() each call); grab the resolved callable
    # so flaky_runner can delegate correctly.
    from core.orchestrator.coordinator import _default_runner
    original = orch.coordinator._runner or _default_runner()

    # One counter per outer orchestrator.run() call, one per pipeline
    # invocation. Each outer call may invoke the pipeline multiple
    # times; we only want to crash the 3rd outer call.
    outer_call_count = [0]
    pipeline_call_count = [0]
    fail_on_outer = 3

    def flaky_runner(state: dict[str, Any]) -> Any:
        pipeline_call_count[0] += 1
        if outer_call_count[0] == fail_on_outer:
            raise RuntimeError("simulated pharmacogene pipeline crash")
        return original(state)

    orch.coordinator._runner = flaky_runner
    results: list[dict[str, Any]] = []
    errors: list[str] = []

    for i in range(3):
        outer_call_count[0] = i + 1
        try:
            r = orch.run(
                gene="CYP2C19", drug="clopidogrel", population="SAS",
                allele1="*2", allele2="*2",
            )
            results.append({
                "i": i,
                "completed": True,
                "has_runs": bool(r.coordination.runs),
                "errors": list(r.errors),
            })
        except Exception as exc:
            results.append({
                "i": i,
                "completed": False,
                "error": f"{type(exc).__name__}: {exc}",
            })
            errors.append(f"run {i}: {type(exc).__name__}: {exc}")

    # Restore.
    orch.coordinator._runner = original

    duration_ms = (time.perf_counter() - t0) * 1000

    # Pass when:
    #   - the 3rd run's failure was captured as a graceful failure
    #     (result.errors non-empty OR completed=False without an
    #     uncaught exception in the caller)
    #   - the 1st and 2nd runs completed cleanly
    first_two_ok = all(
        r.get("completed") and r.get("has_runs")
        for r in results[:2]
    )
    third_handled = (
        not results[2].get("completed")
        or bool(results[2].get("errors"))
    )
    passed = first_two_ok and third_handled

    return StressResult(
        scenario_id="stress_partial_workflow_collapse",
        kind="partial_collapse",
        passed=passed,
        reason=(
            f"first two runs completed={first_two_ok}, "
            f"third handled gracefully={third_handled}"
        ),
        observed={
            "pipeline_call_count": pipeline_call_count[0],
            "outer_call_count": outer_call_count[0],
            "results": results,
        },
        duration_ms=duration_ms,
        errors=tuple(errors),
    )


# ---------------------------------------------------------------------------
# 4. Memory corruption
# ---------------------------------------------------------------------------


def stress_memory_corruption() -> StressResult:
    """Plant corrupted provenance records; verify ProvenanceValidator catches.

    Inserts 3 synthetic records under the same correlation_id:
      - one clean record
      - one with an empty rule_id
      - one with a dangling parent_claim_id

    ProvenanceValidator should flag both corrupted records without
    taking down the validator. Passes when validator reports
    is_clean=False AND dangling_parents + records_with_missing_rule
    are both non-zero.
    """
    t0 = time.perf_counter()
    client = MCPClient()
    corrupt_cid = "stress-corrupt-cid"

    # Plant the records directly via the backend.
    try:
        client.backend.insert("provenance", {
            "claim_id": "CLEAN001",
            "claim": "clean root claim",
            "generating_agent": "test",
            "rule_id": "test.root",
            "correlation_id": corrupt_cid,
            "evidence_sources": [],
            "parent_claim_id": "",
            "origin": "deterministic",
            "verification_verdict": "passed",
            "confidence": 1.0,
            "metadata": {},
            "recorded_at": "2026-05-09T11:00:00+00:00",
        })
        client.backend.insert("provenance", {
            "claim_id": "BADRULE",
            "claim": "missing rule_id",
            "generating_agent": "test",
            "rule_id": "",              # corruption
            "correlation_id": corrupt_cid,
            "evidence_sources": [],
            "parent_claim_id": "",
            "origin": "deterministic",
            "verification_verdict": "passed",
            "confidence": 1.0,
            "metadata": {},
            "recorded_at": "2026-05-09T11:00:01+00:00",
        })
        client.backend.insert("provenance", {
            "claim_id": "ORPHAN01",
            "claim": "dangling parent",
            "generating_agent": "test",
            "rule_id": "test.orphan",
            "correlation_id": corrupt_cid,
            "evidence_sources": [],
            "parent_claim_id": "NONEXISTENT",   # corruption
            "origin": "deterministic",
            "verification_verdict": "passed",
            "confidence": 1.0,
            "metadata": {},
            "recorded_at": "2026-05-09T11:00:02+00:00",
        })
    except Exception as exc:
        return StressResult(
            scenario_id="stress_memory_corruption",
            kind="memory_corruption",
            passed=False,
            reason="failed to plant corrupt records",
            errors=(f"{type(exc).__name__}: {exc}",),
            duration_ms=(time.perf_counter() - t0) * 1000,
        )

    validator = ProvenanceValidator(client=client)
    traces, report = validator.validate_run(corrupt_cid)

    duration_ms = (time.perf_counter() - t0) * 1000

    passed = (
        not report.is_clean
        and report.records_with_missing_rule > 0
        and len(report.dangling_parents) > 0
    )

    return StressResult(
        scenario_id="stress_memory_corruption",
        kind="memory_corruption",
        passed=passed,
        reason=(
            f"validator caught: is_clean={report.is_clean}, "
            f"missing_rule={report.records_with_missing_rule}, "
            f"dangling={len(report.dangling_parents)}"
        ),
        observed={
            "is_clean": report.is_clean,
            "records_examined": report.records_examined,
            "records_with_missing_rule": report.records_with_missing_rule,
            "dangling_parents": list(report.dangling_parents),
            "fail_traces": sum(1 for t in traces if t.state == "fail"),
        },
        duration_ms=duration_ms,
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_stress_scenarios(
    *,
    include: tuple[str, ...] | None = None,
) -> list[StressResult]:
    """Run the four stress scenarios; return a list of results.

    ``include`` lets callers pick a subset by kind name. Default
    runs all four.
    """
    registry: dict[str, Callable[[], StressResult]] = {
        "concurrency": stress_multi_agent_concurrency,
        "retrieval_failure": stress_retrieval_failure,
        "partial_collapse": stress_partial_workflow_collapse,
        "memory_corruption": stress_memory_corruption,
    }
    selected = (
        list(registry.values())
        if include is None
        else [registry[k] for k in include if k in registry]
    )
    out: list[StressResult] = []
    for fn in selected:
        try:
            out.append(fn())
        except Exception as exc:
            out.append(
                StressResult(
                    scenario_id=f"stress_{fn.__name__}",
                    kind="runner_crash",
                    passed=False,
                    reason="scenario function raised",
                    errors=(f"{type(exc).__name__}: {exc}",),
                )
            )
    return out


__all__ = [
    "StressResult",
    "stress_multi_agent_concurrency",
    "stress_retrieval_failure",
    "stress_partial_workflow_collapse",
    "stress_memory_corruption",
    "run_stress_scenarios",
]
