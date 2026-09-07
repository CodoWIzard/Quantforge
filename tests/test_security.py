"""Tenancy / security — blueprint Appendix E minimum test catalogue.

These are the required tests for this subsystem. They are marked xfail until
Weeks 17-18 builds it, so an unimplemented area shows up in the report instead of
looking like passing coverage.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(
    reason="Tenancy / security not implemented yet — Weeks 17-18", strict=False, run=False
)


def test_cross_tenant_query_denied():
    """A query scoped to another tenant returns nothing and is audited."""
    raise NotImplementedError


def test_no_secrets_in_repo():
    """Secret scanning finds nothing committed."""
    raise NotImplementedError


def test_role_checks_enforced():
    """Approval and deployment endpoints require the right role."""
    raise NotImplementedError

