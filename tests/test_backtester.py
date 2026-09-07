"""Backtester — blueprint Appendix E minimum test catalogue.

These are the required tests for this subsystem. They are marked xfail until
Experiment 003 builds it, so an unimplemented area shows up in the report instead of
looking like passing coverage.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(
    reason="Backtester not implemented yet — Experiment 003", strict=False, run=False
)


def test_known_fixture_reproduces():
    """A frozen dataset + known strategy produces the documented trades."""
    raise NotImplementedError


def test_no_lookahead():
    """No signal uses information after its own timestamp."""
    raise NotImplementedError


def test_fee_and_funding_applied_correctly():
    """Costs match a hand-computed expectation."""
    raise NotImplementedError


def test_stop_and_target_priority_policy():
    """When both are hit in one bar, the declared policy decides - not the favourable one."""
    raise NotImplementedError


def test_reproducible_across_runs():
    """Same manifest twice gives byte-identical metrics."""
    raise NotImplementedError

