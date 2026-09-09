"""Contract tests for the Strategy Analyst persona (bots.ANALYST).

The Analyst is the only persona whose product IS the StrategySpec, and its
failure mode is the Builder's one step larger: the Builder invents a missing
field, the Analyst quietly replaces a messy idea with a tidier strategy that
nobody downstream can tell was substituted. Everything after it - the Risk
Reviewer's critique, the backtest, the Director's answer - is then about an idea
the user never had. These tests lock preservation of the user's idea, the
no-gap-filling rule, the conservative reading of ambiguity, the report structure
the Reviewer consumes, and the fence that stops an author from widening the
schema its own output is validated against.

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
    return bots.ANALYST


# --- preserve the idea: the defining failure mode -------------------------

def test_analyst_does_not_rewrite_the_users_idea(persona: str) -> None:
    """A vague idea is easy to 'improve' into something tidy and no longer
    theirs; the substitution is invisible to every later stage."""
    assert "DO NOT REWRITE THE USER'S IDEA INTO A DIFFERENT STRATEGY" in persona
    assert "Preserve the idea and label the unknowns" in persona


def test_rewriting_is_capped_at_making_a_rule_testable(persona: str) -> None:
    """The single licence to edit, and it must stay minimal and disclosed."""
    assert "Rewrite ONLY as much as it" in persona
    assert "say in Open Questions what you changed" in persona


def test_analyst_does_not_fill_gaps(persona: str) -> None:
    """Inherited from the Builder because it is the same fabrication: an
    invented parameter gets tested as if a human chose it."""
    assert "DO NOT FILL GAPS" in persona
    for anti_default in ('not "1h"', 'not "2\npercent"', 'not "RSI"'):
        assert anti_default in persona


def test_missing_values_become_precise_questions(persona: str) -> None:
    assert "Missing information" in persona
    assert "becomes a precise question" in persona


def test_uncertainty_is_never_hidden(persona: str) -> None:
    """The structured template is confident-looking by construction, so a guess
    inside it reads like a decision unless it is flagged."""
    assert "NEVER HIDE UNCERTAINTY" in persona


def test_analyst_gives_no_trading_advice(persona: str) -> None:
    assert "YOU DO NOT DECIDE WHETHER A TRADE SHOULD BE TAKEN" in persona


# --- decision rules -------------------------------------------------------

def test_ambiguity_resolves_to_the_most_conservative_reading(persona: str) -> None:
    """'Conservative' is pinned to smaller risk, not to whichever reading would
    backtest best - otherwise the tiebreak becomes a curve-fit."""
    assert "MOST CONSERVATIVE" in persona
    assert "not the one that would backtest best" in persona


def test_alternatives_are_listed_not_discarded(persona: str) -> None:
    assert "list the alternatives" in persona
    assert "Open Questions" in persona


def test_subjective_reading_becomes_a_measurable_proxy(persona: str) -> None:
    """And the proxy is attributed to the Analyst, not laundered into the user's
    rule set."""
    assert "measurable proxy" in persona
    assert "name the proxy as your choice, not as their rule" in persona


def test_overfitting_is_named_as_a_prohibition(persona: str) -> None:
    """Conditions the idea never asked for cannot be falsified by anyone."""
    assert "Avoid overfitting" in persona
    assert "complexity nobody can falsify" in persona


def test_later_stage_work_is_marked_not_blocking(persona: str) -> None:
    assert "mark it later-stage" in persona


# --- tool boundary --------------------------------------------------------

def test_analyst_does_not_fetch_live_data_unprompted(persona: str) -> None:
    assert "do not fetch live market data unless the Director explicitly allows" in persona


def test_analyst_does_not_backtest_or_invent_results(persona: str) -> None:
    assert "TOOL BOUNDARY" in persona
    assert "do not run backtests yourself" in persona
    assert "never state a data-backed conclusion that" in persona


def test_analyst_will_not_spec_what_it_was_not_given(persona: str) -> None:
    """Same fence as QA and Risk: a spec written from imagination is the most
    convincing possible fabrication, because it is well formatted."""
    assert "Never write\na spec from imagination" in persona


# --- output structure the Risk Reviewer consumes --------------------------

@pytest.mark.parametrize("section", [
    "## StrategySpec",
    "### Summary",
    "### Market",
    "### Setup Conditions",
    "### Entry Logic",
    "### Exit Logic",
    "### Risk Assumptions",
    "### Data Needed",
    "### Open Questions",
    "### Confidence",
])
def test_spec_template_sections_are_present(persona: str, section: str) -> None:
    assert section in persona


@pytest.mark.parametrize("field", [
    "- Asset:", "- Instrument:", "- Timeframe:", "- Session/context:",
    "- Trigger:", "- Confirmation:", "- Avoid entry when:",
    "- Take profit:", "- Stop/invalidation:", "- Time-based exit:",
    "- Position risk:", "- Leverage assumption:", "- Main failure mode:",
    "- Required data:", "- Optional data:", "- Missing information:",
])
def test_spec_template_fields_are_present(persona: str, field: str) -> None:
    """The Risk Reviewer's checklist maps onto these field names; dropping one
    silently removes a thing nobody is left checking."""
    assert field in persona


def test_markdown_override_is_explicit(persona: str) -> None:
    """CONTEXT ends with 'No markdown headers'; this persona's spec is built
    from them, so the override has to be stated or the two rules collide."""
    assert 'overrides the "no markdown headers" instruction above' in persona


def test_handoff_carries_the_four_required_items(persona: str) -> None:
    """The Reviewer acts on the handoff: spec, breaking assumptions, missing
    data, and the one thing to falsify hardest."""
    assert "HANDOFF TO RISK REVIEWER" in persona
    assert "try hardest to\nfalsify" in persona
    assert "do not leave it\nimplied" in persona


def test_handoff_asks_for_falsification_not_improvement(persona: str) -> None:
    assert "falsification, not improvement" in persona


def test_workflow_position_is_stated(persona: str) -> None:
    """Director -> Analyst -> Risk Reviewer -> Director. The Analyst never
    answers the user directly."""
    assert "Research Director -> YOU -> Risk Reviewer" in persona
    assert "the Director synthesises" in persona


# --- inheritance and registration ----------------------------------------

def test_analyst_inherits_shared_context() -> None:
    assert bots.ANALYST.startswith(bots.CONTEXT)


@pytest.mark.parametrize("rule", [
    "NEVER produce authoritative numeric results",
    "NEVER place, modify or simulate orders",
    "Never reveal credentials",
    "NEVER tell anyone you have no memory between messages",
])
def test_shared_guardrails_are_not_dropped(persona: str, rule: str) -> None:
    assert rule in persona


def test_analyst_is_started_with_its_own_token() -> None:
    src = (BOTS_DIR / "bots.py").read_text()
    assert 'QFBot("analyst", ANALYST), ENV["DISCORD_ANALYST_BOT_TOKEN"]' in src
    start = src.index("missing = [")
    assert "DISCORD_ANALYST_BOT_TOKEN" in src[start:start + 400]


def test_analyst_cannot_write_the_schema_that_validates_it() -> None:
    """An author who can widen the definition of 'valid' passes every spec it
    writes; the backtester that grades the idea is fenced off for the same
    reason."""
    import builder
    for path in ("packages/strategy_schema/models.py",
                 "research/backtester/engine.py",
                 "research/validation/verdict.py"):
        _, outside = builder.classify([path], "analyst")
        assert outside == [path], f"{path} must be flagged, not written cleanly"


@pytest.mark.parametrize("path", [
    "experiments/002-strategy-compiler/fixtures.json",
    "data-contracts/strategy-spec.schema.json",
    "tests/test_analyst_persona.py",
])
def test_analyst_owns_specs_fixtures_and_their_tests(path: str) -> None:
    import builder
    forbidden, outside = builder.classify([path], "analyst")
    assert not forbidden and not outside
