"""Unit tests — one file per deterministic module under test.

Scope
-----
Pure-function tests over the deterministic core: rule tables
(sufficiency / verifier / uncertainty), closed-enum boundaries
(boundary / envelope scope firewall), conflict detection,
bias detection, event contracts.

These tests MUST NOT:
    - hit the network
    - call any LLM / generative model
    - depend on file system state outside the repo
    - rely on wall-clock timing semantics
    - import ``demos.*`` (those are integration-level)

If a test needs a full ``SwarmRuntime.run()`` or a flagship demo
signature, it belongs under ``tests/integration/`` instead.
"""
