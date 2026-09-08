"""Contract tests for the QA bot persona (bots.QA).

QA's failure mode is the mirror of the Builder's. The Builder fails by inventing
a rule; QA fails by REPAIRING one - the moment a reviewer supplies the missing
stop, the invented value is laundered through the check and nobody is looking
any more. These lock that fence, and the pass/fail discipline around it.

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
    return bots.QA


# --- the no-repair fence (the whole point of the role) ------------------

def test_qa_is_forbidden_from_fixing_anything(persona: str) -> None:
    assert "MUST NEVER DO IS FIX ANYTHING" in persona
    assert "If you find yourself writing a" in persona


def test_the_laundering_failure_is_named_explicitly(persona: str) -> None:
    """"I fixed the missing stop by adding 2 percent" passes an invented rule
    through the one check meant to catch it."""
    assert "I fixed the missing stop by adding 2 percent" in persona
    assert "launders an invented rule" in persona


def test_required_fixes_are_requirements_not_replacement_content(persona: str) -> None:
    assert "never as replacement content you wrote" in persona


def test_qa_does_not_rewrite_the_strategy(persona: str) -> None:
    assert "You do not rewrite the" in persona


# --- the six checks ------------------------------------------------------

@pytest.mark.parametrize("check", [
    "JSON validity",
    "Required fields",
    "Scope",
    "Invented rules",
    "Clarification behaviour",
    "Demonstrability",
])
def test_all_six_checks_are_specified(persona: str, check: str) -> None:
    assert check in persona


@pytest.mark.parametrize("field", [
    "market", "timeframe", "direction", "entry", "exit", "risk", "assumptions",
])
def test_the_seven_required_fields_are_named(persona: str, field: str) -> None:
    assert field in persona


def test_missing_field_without_a_question_is_a_fail(persona: str) -> None:
    """The subtle case: listing a field in missing_fields is not enough on its
    own - an unasked question leaves the human with nothing to answer."""
    assert "no question asked is a fail" in persona


def test_disclosed_and_hidden_assumptions_are_distinguished(persona: str) -> None:
    """assumptions_used is a disclosure channel; the same inference hidden inside
    strategy_spec is the actual defect."""
    assert "assumptions_used" in persona
    assert "hidden one" in persona


def test_a_plausible_default_still_counts_as_invented(persona: str) -> None:
    assert "A plausible default is still invented" in persona


# --- verdict discipline ---------------------------------------------------

def test_only_two_verdicts_exist(persona: str) -> None:
    assert "There is no third verdict" in persona
    assert '"pass | fail"' in persona


def test_fails_must_name_a_concrete_defect(persona: str) -> None:
    assert "every fail must name a concrete defect" in persona


def test_an_empty_fail_report_is_rejected(persona: str) -> None:
    """status:fail with every array empty tells the Builder nothing."""
    assert "at least one array must be non-empty" in persona


def test_bad_qa_behaviour_is_shown_not_just_described(persona: str) -> None:
    assert "Looks fine" in persona


def test_output_schema_keys_are_all_present(persona: str) -> None:
    for key in ("status", "schema_errors", "missing_required_fields",
                "invented_rule_risks", "scope_violations",
                "clarification_failures", "required_fixes", "approval_summary"):
        assert f'"{key}"' in persona


# --- scope ----------------------------------------------------------------

def test_month_one_scope_drift_is_a_fail(persona: str) -> None:
    for later in ("Azure", "billing", "SaaS", "Redis", "production architecture"):
        assert later in persona


def test_btc_eth_perps_only(persona: str) -> None:
    assert "BTC or ETH perpetual futures" in persona


def test_qa_will_not_review_what_it_cannot_see(persona: str) -> None:
    """Reviewing an artifact from imagination produces a confident verdict about
    something that was never said."""
    assert "never review from" in persona


# --- inheritance and registration ----------------------------------------

def test_qa_inherits_shared_context() -> None:
    assert bots.QA.startswith(bots.CONTEXT)


@pytest.mark.parametrize("rule", [
    "NEVER produce authoritative numeric results",
    "NEVER place, modify or simulate orders",
    "Never reveal credentials",
    "NEVER tell anyone you have no memory between messages",
])
def test_shared_guardrails_are_not_dropped(persona: str, rule: str) -> None:
    assert rule in persona


def test_json_override_is_explicit(persona: str) -> None:
    assert "this overrides the plain-text instruction above" in persona


def test_qa_is_started_with_its_own_token() -> None:
    src = (BOTS_DIR / "bots.py").read_text()
    assert 'QFBot("qa", QA), ENV["DISCORD_QA_BOT_TOKEN"]' in src
    start = src.index("missing = [")
    assert "DISCORD_QA_BOT_TOKEN" in src[start:start + 400]


def test_qa_cannot_write_the_schema_it_reviews() -> None:
    """Same self-marking fence as the Builder, pointed the other way."""
    import builder
    for path in ("packages/strategy_schema/models.py",
                 "experiments/002-strategy-compiler/run_v3_demos.py"):
        _, outside = builder.classify([path], "qa")
        assert outside == [path]


def test_qa_owns_validators_and_fixtures() -> None:
    import builder
    for path in ("tests/test_strategy_compiler.py", "data-contracts/spec.json"):
        forbidden, outside = builder.classify([path], "qa")
        assert not forbidden and not outside
