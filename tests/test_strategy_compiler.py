"""Strategy compiler — blueprint Appendix E minimum test catalogue.

These are the required tests for this subsystem. They are marked xfail until
Experiment 002 builds it, so an unimplemented area shows up in the report instead of
looking like passing coverage.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(
    reason="Strategy compiler not implemented yet — Experiment 002", strict=False, run=False
)


def test_missing_parameter_raises_and_asks():
    """A missing threshold produces a question, never a default value."""
    raise NotImplementedError


def test_invalid_indicator_rejected():
    """An expression outside SUPPORTED_INDICATORS is rejected, not evaluated."""
    raise NotImplementedError


def test_impossible_risk_values_rejected():
    """risk_per_trade > daily_loss_limit is contradictory and must fail."""
    raise NotImplementedError


def test_same_input_same_spec():
    """Deterministic: identical candidate compiles to an identical spec hash."""
    raise NotImplementedError

