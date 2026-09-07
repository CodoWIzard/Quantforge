"""Validation — blueprint Appendix E minimum test catalogue.

These are the required tests for this subsystem. They are marked xfail until
Weeks 11-12 builds it, so an unimplemented area shows up in the report instead of
looking like passing coverage.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(
    reason="Validation not implemented yet — Weeks 11-12", strict=False, run=False
)


def test_out_of_sample_split_is_disjoint():
    """Train and test windows never overlap."""
    raise NotImplementedError


def test_parameter_sweep_respects_bounds():
    """A sweep cannot leave the declared parameter space."""
    raise NotImplementedError


def test_regime_labels_are_stable():
    """Regime assignment is deterministic for a given dataset version."""
    raise NotImplementedError


def test_concentration_flagged():
    """A result driven by three trades is flagged, not passed."""
    raise NotImplementedError

