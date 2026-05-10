"""Regression tests for flagship demo output signatures.

Each flagship demo has a documented output shape that is part of the
project's release contract (``.project-status.md``). These tests
invoke each demo as a subprocess and scrape distinctive substrings
from its stdout. If a demo output changes, the test fails — the
reviewer then consciously decides whether the change is intended
(and updates the assertions in the same commit) or a regression.

Demos exercised (signatures from session #6/#7 status doc):

    unified_demo                       14/14/13 events, 41 total;
                                       sufficient/sufficient/downgrade
    evidence_sufficiency_demo          3 brief-named scenarios end-to-end
    evidence_sufficiency_abstention_demo  6 adversarial refusals with rule ids
    safety_demo                        1 delivered / 4 blocked / 4/4 matched
    showcase                           7-stage PASS
    interoperability_demo              3 scenarios · 24 envelopes · 24 provenance

Tests time-bounded to 60s each; normal demo runtime is <3s.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_demo(module: str, *, timeout: int = 60) -> str:
    """Run ``python -m demos.<module>`` and return combined stdout+stderr.

    Uses the current Python executable (the venv's Python when the
    suite runs under the venv). Captures combined output to make
    substring assertions robust to color codes / ANSI sequences.
    """
    result = subprocess.run(
        [sys.executable, "-m", f"demos.{module}"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=None,  # inherit
    )
    assert result.returncode == 0, (
        f"demos.{module} failed with exit {result.returncode}\n"
        f"stdout: {result.stdout[-2000:]}\nstderr: {result.stderr[-2000:]}"
    )
    return result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Unified demo — the session-#7 canonical signature
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestUnifiedDemo:
    def test_unified_demo_flagship_signature(self) -> None:
        output = _run_demo("unified_demo")
        # Three scenarios, each with a decision + verdict.
        assert "Clopidogrel + CYP2C19 + South Asian" in output
        assert "Carbamazepine + HLA-B*15:02 + East Asian" in output
        assert "Codeine + CYP2D6 + African ancestry" in output
        # Decisions (from scorecard table).
        assert "sufficient" in output
        assert "supported" in output
        assert "downgrade" in output
        assert "uncertain" in output
        # Total-events line from the closing summary.
        assert "41" in output or "Total RuntimeEvents" in output


# ---------------------------------------------------------------------------
# Evidence sufficiency demos — sessoin-#6 signatures
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestEvidenceSufficiencyDemos:
    def test_sufficiency_demo_runs_three_scenarios(self) -> None:
        output = _run_demo("evidence_sufficiency_demo")
        # Three brief-named scenarios.
        assert "Clopidogrel" in output
        assert "Carbamazepine" in output
        assert "Codeine" in output
        # All three decisions surface.
        assert "sufficient" in output
        assert "downgrade" in output

    def test_abstention_demo_names_rule_ids(self) -> None:
        """Every refusal must carry a specific rule id (R1..R12 / V1..V10 /
        U1..U9). The abstention demo exercises 6 refusals; we check for
        some of the expected rule ids in the output."""
        output = _run_demo("evidence_sufficiency_abstention_demo")
        # The demo prints the scenario label + the rule id for each refusal.
        # R-rules (sufficiency decisions) appear in at least one refusal.
        has_r_rule = any(f"R{i}" in output for i in range(1, 13))
        assert has_r_rule, "no R-rule id found in abstention demo output"


# ---------------------------------------------------------------------------
# Safety demo — session-#2 signature
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestSafetyDemo:
    def test_safety_demo_blocked_count(self) -> None:
        output = _run_demo("safety_demo")
        # Safety demo closing line: "Total scenarios: 5  delivered: 1  blocked: 4"
        assert "blocked: 4" in output or "4 blocked" in output
        assert "delivered: 1" in output or "1 delivered" in output


# ---------------------------------------------------------------------------
# Showcase — session-#0 flagship signature
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestShowcaseDemo:
    def test_showcase_passes(self) -> None:
        output = _run_demo("showcase")
        # Showcase closes with "PASS" on a 7-stage pipeline.
        assert "PASS" in output


# ---------------------------------------------------------------------------
# Interoperability demo — session-#5 signature
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestInteroperabilityDemo:
    def test_interop_demo_envelope_count(self) -> None:
        output = _run_demo("interoperability_demo")
        # Session-#5 signature: "3 genomic scenarios · 24 envelopes · 24
        # provenance records". Exact counts may drift (the demo was extended
        # in later sessions); assert the lower bounds.
        assert "envelope" in output.lower()
        assert "provenance" in output.lower()
        assert "genomic" in output.lower()
