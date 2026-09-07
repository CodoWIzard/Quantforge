"""Execution — blueprint Appendix E minimum test catalogue.

These are the required tests for this subsystem. They are marked xfail until
Experiment 009 builds it, so an unimplemented area shows up in the report instead of
looking like passing coverage.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(
    reason="Execution not implemented yet — Experiment 009", strict=False, run=False
)


def test_submit_is_idempotent():
    """A retried submit after timeout does not double the position."""
    raise NotImplementedError


def test_rejected_order_handled():
    """A venue rejection is recorded and does not corrupt local state."""
    raise NotImplementedError


def test_partial_fill_accounted():
    """Partial fills reconcile to the correct net position."""
    raise NotImplementedError


def test_reconnect_reconciles():
    """After reconnect, local state is rebuilt from exchange truth."""
    raise NotImplementedError


def test_exchange_mismatch_fails_closed():
    """Disagreement between local and venue state stops new orders."""
    raise NotImplementedError

