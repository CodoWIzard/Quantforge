"""Cost — blueprint Appendix E minimum test catalogue.

These are the required tests for this subsystem. They are marked xfail until
Weeks 9-10 builds it, so an unimplemented area shows up in the report instead of
looking like passing coverage.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(
    reason="Cost not implemented yet — Weeks 9-10", strict=False, run=False
)


def test_every_job_records_cost():
    """No job completes without a cost ledger entry (§50)."""
    raise NotImplementedError


def test_credit_limits_applied():
    """A request beyond the plan allowance is refused with 402, not run."""
    raise NotImplementedError

