"""Integration tests — full lifecycle + flagship signature regression.

Scope
-----
Tests that run a full ``SwarmRuntime.run()`` against the real
in-tree seed data, or that invoke a demo's main() to confirm its
output signature is unchanged.

Each flagship demo has a pinned signature documented in
``.project-status.md``. The regression tests in this directory
enforce those signatures are byte-stable across commits — if a
demo output changes, the test fails loudly so reviewers look at
the diff.
"""
