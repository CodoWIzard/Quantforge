"""Risk engine — blueprint Appendix E minimum test catalogue.

These are the required tests for this subsystem. They are marked xfail until
Weeks 13-14 builds it, so an unimplemented area shows up in the report instead of
looking like passing coverage.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(
    reason="Risk engine not implemented yet — Weeks 13-14", strict=False, run=False
)


def test_max_position_enforced():
    """An intent exceeding max_open_positions is denied."""
    raise NotImplementedError


def test_daily_loss_limit_halts_trading():
    """Once breached, no new intent is allowed for the day."""
    raise NotImplementedError


def test_stale_data_fails_closed():
    """Data older than the staleness bound blocks new orders."""
    raise NotImplementedError


def test_duplicate_order_rejected():
    """Same idempotency key cannot open two positions."""
    raise NotImplementedError


def test_kill_switch_blocks_everything():
    """After kill, every intent is denied regardless of other state."""
    raise NotImplementedError

