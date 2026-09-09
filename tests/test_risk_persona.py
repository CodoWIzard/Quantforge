"""Contract tests for the Risk Reviewer persona (bots.RISK).

The Risk Reviewer's failure mode is the third distinct one in this service. The
Builder fails by inventing a rule; QA fails by repairing one; the Reviewer fails
by APPROVING a spec because it reads plausibly. A critique that waves through a
well-worded idea produces the same outcome as no review at all, except that now
a verdict is on record. These tests lock the falsification-first discipline, the
report structure the Director consumes, and the fence that stops a critic from
editing the artifacts it judges.

Static analysis of the persona string. No network, no Discord, no model call.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BOTS_DIR = Path(__file__).resolve().parents[1] / "services" / "discord-bots"
sys.path.insert(0, str(BOTS_DIR))

pytest.importorskip("discord")
import bots  # noqa: E402


@pytest.fixture(scope="module")
def persona() -> str:
    return bots.RISK


# --- falsification-first: the whole point of the role --------------------

def test_plausibility_is_not_approval(persona: str) -> None:
    """The named failure mode. A reviewer that passes anything well-worded has
    replaced review with proofreading."""
    assert "NEVER APPROVE SOMETHING BECAUSE IT SOUNDS PLAUSIBLE" in persona


def test_a_clean_review_still_lists_residual_risks(persona: str) -> None:
    """An empty risk list is an unfinished review, not a clean bill of health -
    otherwise 'nothing jumped out' becomes an approval."""
    assert "still list the residual risks" in persona


def test_reviewer_does_not_rewrite_the_strategy(persona: str) -> None:
    """Naming the defect is the output; supplying the missing stop launders an
    invented rule through the reviewer."""
    assert "DO NOT REWRITE THE STRATEGY" in persona
    assert "Supplying the" in persona


def test_real_risks_are_separated_from_vague_concerns(persona: str) -> None:
    """'Crypto is volatile' is not a finding. Every risk must attach to
    something concrete in the spec."""
    assert "SEPARATE REAL RISKS FROM VAGUE CONCERNS" in persona
    assert "is not a finding" in persona


def test_ambiguity_counts_as_trading_risk_not_style(persona: str) -> None:
    """Wording is out of scope, EXCEPT when two people would implement the rule
    differently - that ambiguity is a real execution risk."""
    assert "two people would implement differently" in persona


def test_vague_assumptions_become_validation_questions(persona: str) -> None:
    assert "TURN VAGUE ASSUMPTIONS INTO VALIDATION QUESTIONS" in persona


# --- verdict decision rules ---------------------------------------------

def test_missing_entry_or_invalidation_forces_needs_revision(persona: str) -> None:
    """Without entry AND invalidation there is no measurable risk, so no verdict
    other than Needs revision is honest."""
    assert "No clear entry AND invalidation logic -> Needs revision" in persona


def test_unproven_is_not_a_reason_to_reject(persona: str) -> None:
    """Testable-but-unproven is what the test loop exists for; rejecting it
    would stop every new idea at the critic."""
    assert "Ready to test WITH caveats" in persona
    assert "Unproven is not a reason" in persona


def test_reject_is_scoped_to_unevaluable_not_unconvincing(persona: str) -> None:
    """'Reject for now' must not become a taste verdict."""
    assert "not for ideas you find unconvincing" in persona


def test_live_money_dependency_is_marked_later_stage(persona: str) -> None:
    assert "later-stage work" in persona


# --- tool boundary -------------------------------------------------------

def test_checked_facts_are_distinguished_from_suspicions(persona: str) -> None:
    """The reviewer may request deterministic checks, but presenting a suspicion
    as a measured result is the same fabrication ADR-003 forbids."""
    assert "distinguish a checked fact" in persona
    assert "unvalidated concern" in persona


def test_deterministic_tools_own_the_measurements(persona: str) -> None:
    assert "TOOL BOUNDARY" in persona
    for measure in ("volatility", "max drawdown", "liquidation"):
        assert measure in persona


def test_reviewer_will_not_review_what_it_cannot_see(persona: str) -> None:
    """Same fence as QA: a confident verdict about an artifact that was never
    pasted is worse than asking for it."""
    assert "Never review from imagination" in persona


# --- output structure the Director consumes ------------------------------

@pytest.mark.parametrize("section", [
    "## Risk Review",
    "### Verdict",
    "### Main Failure Modes",
    "### Weak Assumptions",
    "### Market Regime Risks",
    "### Execution Risks",
    "### Missing Data",
    "### Suggested Deterministic Checks",
    "### Revision Requests",
    "### Confidence In Review",
])
def test_review_template_sections_are_present(persona: str, section: str) -> None:
    assert section in persona


def test_markdown_override_is_explicit(persona: str) -> None:
    """CONTEXT ends with 'No markdown headers'; this persona's report is built
    from them, so the override has to be stated or the two rules collide."""
    assert 'overrides the "no markdown headers" instruction above' in persona


def test_handoff_carries_the_four_required_items(persona: str) -> None:
    """The Director acts on the handoff, so verdict, top risks, required checks
    and the can-we-answer-now line must all be mandatory."""
    assert "HANDOFF TO RESEARCH DIRECTOR" in persona
    assert "coherent final research response now" in persona
    assert "do not leave it implied" in persona


# --- inheritance and registration ----------------------------------------

def test_risk_inherits_shared_context() -> None:
    assert bots.RISK.startswith(bots.CONTEXT)


@pytest.mark.parametrize("rule", [
    "NEVER produce authoritative numeric results",
    "NEVER place, modify or simulate orders",
    "Never reveal credentials",
    "NEVER tell anyone you have no memory between messages",
])
def test_shared_guardrails_are_not_dropped(persona: str, rule: str) -> None:
    assert rule in persona


def test_risk_is_started_with_its_own_token() -> None:
    src = (BOTS_DIR / "bots.py").read_text()
    assert 'QFBot("risk", RISK), ENV["DISCORD_RISK_BOT_TOKEN"]' in src
    start = src.index("missing = [")
    assert "DISCORD_RISK_BOT_TOKEN" in src[start:start + 400]


def test_risk_cannot_write_the_artifacts_it_judges() -> None:
    """A critic that can edit the spec, the experiments or the engine that
    grades them is marking its own homework from the other direction."""
    import builder
    for path in ("packages/strategy_schema/models.py",
                 "experiments/002-strategy-compiler/run_v3_demos.py",
                 "research/backtester/engine.py"):
        _, outside = builder.classify([path], "risk")
        assert outside == [path], f"{path} must be flagged, not written cleanly"


@pytest.mark.parametrize("path", [
    "docs/decisions/ADR-011-risk-review.md",
    "tests/test_risk_persona.py",
])
def test_risk_owns_review_criteria_and_their_tests(path: str) -> None:
    import builder
    forbidden, outside = builder.classify([path], "risk")
    assert not forbidden and not outside
