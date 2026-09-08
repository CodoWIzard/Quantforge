"""Contract tests for the Builder bot persona (bots.BUILDER).

The Builder's whole value is refusing to fill gaps: a draft with three invented
parameters looks finished, so nobody checks it. These lock the contract Jayden
specified so a future prompt edit cannot quietly soften it.

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
    return bots.BUILDER


# --- the seven required fields -----------------------------------------

@pytest.mark.parametrize("field", [
    "market", "timeframe", "direction", "entry", "exit", "risk", "assumptions",
])
def test_all_seven_required_fields_are_named(persona: str, field: str) -> None:
    assert field in persona


def test_missing_fields_go_to_a_list_not_a_guess(persona: str) -> None:
    assert "missing_fields" in persona
    assert "clarification_questions" in persona


def test_status_values_are_specified(persona: str) -> None:
    for status in ("draft_created", "needs_clarification", "blocked"):
        assert status in persona


def test_output_schema_keys_are_all_present(persona: str) -> None:
    for key in ("status", "strategy_spec", "missing_fields",
                "clarification_questions", "assumptions_used", "notes_for_qa"):
        assert f'"{key}"' in persona


# --- the anti-invention rules (the point of the role) -------------------

def test_the_worked_failure_case_is_spelled_out(persona: str) -> None:
    """"Buy BTC when price breaks resistance" answered with 1h/2%/RSI is the
    exact failure this bot exists to prevent - naming it beats abstract rules."""
    assert "breaks resistance" in persona
    assert "RSI" in persona and "2 percent" in persona


def test_named_defaults_are_forbidden_by_example(persona: str) -> None:
    assert 'A missing timeframe is not "1h"' in persona


def test_assumptions_used_cannot_hold_the_bots_own_guesses(persona: str) -> None:
    """Otherwise 'assumptions_used' becomes a laundering channel for invention."""
    assert "never things you decided yourself" in persona


def test_bad_clarification_questions_are_shown_not_just_described(persona: str) -> None:
    assert "Can you clarify?" in persona
    assert "I will assume 1h." in persona


def test_spec_is_never_valid_with_missing_fields(persona: str) -> None:
    assert "Never report a spec as valid while a required field is" in persona


# --- scope ---------------------------------------------------------------

def test_market_scope_is_btc_and_eth_perps(persona: str) -> None:
    assert "BTC perpetual futures" in persona
    assert "ETH perpetual futures" in persona


def test_out_of_scope_market_blocks(persona: str) -> None:
    assert "blocked" in persona


def test_direction_values_are_enumerated(persona: str) -> None:
    assert "long, short, both" in persona


def test_later_stage_work_is_refused(persona: str) -> None:
    for later in ("Azure", "Foundry", "billing", "managed Redis"):
        assert later in persona


def test_director_is_not_bypassed(persona: str) -> None:
    assert "do not bypass the Director" in persona.replace("You do not bypass",
                                                           "you do not bypass")


# --- it still inherits every shared guardrail ---------------------------

def test_builder_inherits_shared_context() -> None:
    assert bots.BUILDER.startswith(bots.CONTEXT)


@pytest.mark.parametrize("rule", [
    "NEVER produce authoritative numeric results",
    "NEVER place, modify or simulate orders",
    "Never reveal credentials",
    "NEVER tell anyone you have no memory between messages",
])
def test_shared_guardrails_are_not_dropped(persona: str, rule: str) -> None:
    assert rule in persona


def test_json_output_overrides_only_the_plain_text_instruction(persona: str) -> None:
    """The Builder answers in JSON, which contradicts CONTEXT's 'plain text, no
    markdown'. That override must be explicit, so a reader knows it is intended
    rather than a conflict nobody noticed."""
    assert "this overrides the plain-text instruction above" in persona


# --- registration --------------------------------------------------------

def test_builder_is_started_with_its_own_token() -> None:
    src = (BOTS_DIR / "bots.py").read_text()
    assert 'QFBot("builder", BUILDER), ENV["DISCORD_BUILDER_BOT_TOKEN"]' in src
    assert '"DISCORD_BUILDER_BOT_TOKEN"' in src


def test_missing_builder_token_fails_loudly() -> None:
    """A bot that silently does not start looks online-but-deaf to the humans."""
    src = (BOTS_DIR / "bots.py").read_text()
    start = src.index("missing = [")
    assert "DISCORD_BUILDER_BOT_TOKEN" in src[start:start + 400]
