"""Data ingestion — blueprint Appendix E minimum test catalogue.

These are the required tests for this subsystem. They are marked xfail until
Experiment 008 builds it, so an unimplemented area shows up in the report instead of
looking like passing coverage.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(
    reason="Data ingestion not implemented yet — Experiment 008", strict=False, run=False
)


def test_reconnect_resumes_without_loss():
    """A dropped WebSocket resumes and backfills the missed window."""
    raise NotImplementedError


def test_duplicate_event_deduplicated():
    """Same sequence number twice is stored once."""
    raise NotImplementedError


def test_out_of_order_timestamp_handled():
    """Events arriving out of order are ordered by ts_utc, not arrival."""
    raise NotImplementedError


def test_gap_detected_not_interpolated():
    """A gap is recorded as a gap. Never filled silently."""
    raise NotImplementedError


def test_schema_migration_is_versioned():
    """MarketEvent schema_version bump is handled explicitly."""
    raise NotImplementedError

