"""roster_facts must state the ADR-011 transition, and state it honestly.

WHY THIS TEST EXISTS: asked whether it had taken over the other bots' jobs, the
Director described the live five-stage chain correctly - because nobody had told
it about the architecture decision. The fix is a fact block, not a persona edit.

The invariant is narrower than "mention ADR-011". The dangerous failure is the
OPPOSITE one: a Director that reads the decision and announces it has already
absorbed falsification and QA, while the Risk Reviewer and QA bot are still the
only things performing those checks. Authority it does not have is worse than
ignorance. So the block must carry BOTH the decision and its unexecuted status.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BOTS_DIR = REPO / "services" / "discord-bots"
sys.path.insert(0, str(BOTS_DIR))

bots = pytest.importorskip("bots", reason="discord.py not installed")


def test_roster_names_the_decision() -> None:
    facts = bots.roster_facts()
    assert "ADR-011" in facts
    assert "supersedes ADR-007" in facts


def test_roster_says_what_is_done_and_what_is_not() -> None:
    """Half-executed is the most misleading state to be in.

    The /research chain IS Director-only now; the specialists are still alive on
    @mention and /build still routes to the Builder. A bot that knows only the
    first half claims a takeover that has not happened; one that knows only the
    second denies a change that has.
    """
    facts = bots.roster_facts()
    assert "PARTIALLY DONE" in facts
    assert "already Director-only" in facts
    assert "still running and still do their jobs" in facts


def test_roster_keeps_build_on_the_builder() -> None:
    """/build is not part of the collapse. The Builder still owns code writing,
    and it is the only path that opens a PR."""
    facts = bots.roster_facts()
    assert "/build is UNCHANGED" in facts
    assert "only path" in facts


def test_roster_states_the_self_review_consequence() -> None:
    """A four-stage transcript by one agent is not four opinions."""
    facts = bots.roster_facts()
    assert "not independent" in facts


def test_roster_names_the_blocking_precondition() -> None:
    """A plan without its blocker reads as an announcement."""
    facts = bots.roster_facts()
    assert "ZERO of them exist yet" in facts
    assert "NotImplementedError" in facts


def test_roster_forbids_claiming_absorbed_authority() -> None:
    facts = bots.roster_facts()
    assert "must NOT claim it has taken over" in facts


def test_adr_011_exists_and_is_not_marked_executed() -> None:
    adr = REPO / "docs" / "decisions" / "ADR-011-the-director-absorbs-the-specialist-roles.md"
    assert adr.exists(), "roster_facts points bots at this file; it must exist"
    text = adr.read_text()
    assert "transition NOT yet executed" in text
    assert "Supersedes: ADR-007" in text
