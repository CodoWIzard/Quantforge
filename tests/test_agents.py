"""Agents — blueprint Appendix E minimum test catalogue.

These are the required tests for this subsystem. They are marked xfail until
Weeks 9-10 builds it, so an unimplemented area shows up in the report instead of
looking like passing coverage.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xfail(
    reason="Agents not implemented yet — Weeks 9-10", strict=False, run=False
)


def test_correct_tool_chosen():
    """The right tool with the right arguments for the scenario."""
    raise NotImplementedError


def test_output_matches_schema():
    """Every response validates against the agent's output schema."""
    raise NotImplementedError


def test_resists_prompt_injection():
    """Instructions embedded in data are ignored and reported."""
    raise NotImplementedError


def test_no_unsupported_claims():
    """No metric is stated that a tool did not return."""
    raise NotImplementedError


def test_escalates_on_ambiguity():
    """An underspecified request produces questions, not assumptions."""
    raise NotImplementedError

